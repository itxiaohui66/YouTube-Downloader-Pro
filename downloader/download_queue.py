"""下载队列管理模块

使用 ThreadPoolExecutor 实现并发下载管理，
支持任务排队、暂停、恢复、取消和重试功能。
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from queue import Queue, PriorityQueue
from typing import Dict, List, Optional, Callable

from ..models.task import DownloadTask, TaskStatus, DownloadProgress

logger = logging.getLogger(__name__)


class DownloadQueue:
    """下载队列管理器

    基于 ThreadPoolExecutor 实现多线程并发下载，
    提供任务队列管理、进度追踪和状态控制。

    特性:
    - 支持 1-32 线程并发
    - 任务优先级排序
    - 实时进度回调
    - 暂停/恢复/取消操作
    - 失败任务重试
    """

    def __init__(self, max_workers: int = 4) -> None:
        """初始化下载队列

        Args:
            max_workers: 最大并发下载线程数 (1-32)
        """
        self._max_workers = max(1, min(max_workers, 32))
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Future] = {}  # task_id -> Future
        self._tasks: Dict[str, DownloadTask] = {}  # task_id -> DownloadTask

        # 暂停队列中等待执行的任务
        self._pending_tasks: List[DownloadTask] = []

        # 回调
        self._on_task_started: Optional[Callable[[DownloadTask], None]] = None
        self._on_task_progress: Optional[Callable[[DownloadTask, DownloadProgress, str], None]] = None
        self._on_task_completed: Optional[Callable[[DownloadTask], None]] = None
        self._on_task_failed: Optional[Callable[[DownloadTask], None]] = None
        self._on_all_completed: Optional[Callable[[], None]] = None

        # 状态
        self._is_paused = False
        self._is_running = False
        self._lock = threading.RLock()

    # ========== 属性 ==========

    @property
    def max_workers(self) -> int:
        """最大并发数"""
        return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int) -> None:
        """设置最大并发数"""
        self._max_workers = max(1, min(value, 32))

    @property
    def is_running(self) -> bool:
        """队列是否正在运行"""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """队列是否已暂停"""
        return self._is_paused

    @property
    def task_count(self) -> int:
        """队列中的总任务数"""
        return len(self._tasks)

    @property
    def active_tasks(self) -> List[DownloadTask]:
        """获取所有活动中的任务"""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.status in (TaskStatus.DOWNLOADING, TaskStatus.MERGING)
            ]

    @property
    def pending_tasks(self) -> List[DownloadTask]:
        """获取所有等待中的任务"""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.status == TaskStatus.WAITING
            ]

    @property
    def completed_tasks(self) -> List[DownloadTask]:
        """获取所有已完成的任务"""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.status == TaskStatus.COMPLETED
            ]

    @property
    def failed_tasks(self) -> List[DownloadTask]:
        """获取所有失败的任务"""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.status == TaskStatus.FAILED
            ]

    # ========== 回调设置 ==========

    def set_callbacks(
        self,
        on_started: Optional[Callable[[DownloadTask], None]] = None,
        on_progress: Optional[Callable[[DownloadTask, DownloadProgress, str], None]] = None,
        on_completed: Optional[Callable[[DownloadTask], None]] = None,
        on_failed: Optional[Callable[[DownloadTask], None]] = None,
        on_all_completed: Optional[Callable[[], None]] = None,
    ) -> None:
        """设置回调函数

        Args:
            on_started: 任务开始回调
            on_progress: 任务进度回调
            on_completed: 任务完成回调
            on_failed: 任务失败回调
            on_all_completed: 全部完成回调
        """
        self._on_task_started = on_started
        self._on_task_progress = on_progress
        self._on_task_completed = on_completed
        self._on_task_failed = on_failed
        self._on_all_completed = on_all_completed

    # ========== 任务管理 ==========

    def add_task(self, task: DownloadTask) -> None:
        """添加下载任务到队列

        Args:
            task: 下载任务对象
        """
        with self._lock:
            task.status = TaskStatus.WAITING
            self._tasks[task.task_id] = task

        logger.info(f"任务已添加: {task.task_id} - {task.url[:60]}")

    def add_tasks(self, tasks: List[DownloadTask]) -> None:
        """批量添加下载任务

        Args:
            tasks: 下载任务列表
        """
        for task in tasks:
            self.add_task(task)

    def remove_task(self, task_id: str) -> bool:
        """移除下载任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功移除
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]

            # 不能移除正在下载的任务
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.MERGING):
                return False

            del self._tasks[task_id]
            logger.info(f"任务已移除: {task_id}")
            return True

    def clear_completed(self) -> int:
        """清空已完成的任务

        Returns:
            清除的任务数量
        """
        with self._lock:
            completed_ids = [
                tid for tid, t in self._tasks.items()
                if t.status == TaskStatus.COMPLETED
            ]
            for tid in completed_ids:
                del self._tasks[tid]

            logger.info(f"已清除 {len(completed_ids)} 个已完成任务")
            return len(completed_ids)

    def clear_failed(self) -> int:
        """清空失败的任务

        Returns:
            清除的任务数量
        """
        with self._lock:
            failed_ids = [
                tid for tid, t in self._tasks.items()
                if t.status == TaskStatus.FAILED
            ]
            for tid in failed_ids:
                del self._tasks[tid]

            logger.info(f"已清除 {len(failed_ids)} 个失败任务")
            return len(failed_ids)

    def clear_all(self) -> None:
        """清空所有任务（不会取消正在下载的任务）"""
        with self._lock:
            active_ids = {
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.DOWNLOADING, TaskStatus.MERGING)
            }
            # 保留活动任务
            self._tasks = {
                tid: t for tid, t in self._tasks.items()
                if tid in active_ids
            }

    # ========== 队列控制 ==========

    def start(self, download_func: Callable[[DownloadTask], bool]) -> None:
        """启动下载队列

        创建线程池并开始处理队列中的任务。

        Args:
            download_func: 下载函数，接收 DownloadTask 返回 bool
        """
        if self._is_running:
            logger.warning("队列已在运行中")
            return

        with self._lock:
            self._is_running = True
            self._is_paused = False

            # 创建线程池
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

            # 提交所有等待中的任务
            waiting_tasks = self.pending_tasks
            for task in waiting_tasks:
                self._submit_task(task, download_func)

            # 提交暂存的任务
            for task in self._pending_tasks:
                self._submit_task(task, download_func)
            self._pending_tasks.clear()

        logger.info(f"下载队列已启动 (workers={self._max_workers})")

        # 启动监控线程（用于检测全部完成）
        threading.Thread(
            target=self._monitor_completion,
            daemon=True,
            name="queue-monitor",
        ).start()

    def stop(self) -> None:
        """停止下载队列"""
        with self._lock:
            self._is_running = False

            # 取消所有未开始的任务
            for task in self._tasks.values():
                if task.status == TaskStatus.WAITING:
                    task.status = TaskStatus.CANCELLED

            # 关闭线程池
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None

        logger.info("下载队列已停止")

    def pause_all(self) -> None:
        """暂停所有下载"""
        self._is_paused = True
        logger.info("所有下载已暂停")

    def resume_all(self) -> None:
        """恢复所有下载"""
        self._is_paused = False
        logger.info("所有下载已恢复")

    def cancel_task(self, task_id: str) -> bool:
        """取消指定任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            future = self._futures.get(task_id)

            if task.status == TaskStatus.WAITING and future:
                future.cancel()
                task.status = TaskStatus.CANCELLED
                return True

            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.MERGING):
                # 标记为取消，实际取消由下载器处理
                task.status = TaskStatus.CANCELLED
                return True

            return False

    def retry_failed(self, download_func: Callable[[DownloadTask], bool]) -> int:
        """重试所有失败的任务

        Args:
            download_func: 下载函数

        Returns:
            重试的任务数量
        """
        with self._lock:
            failed = self.failed_tasks
            for task in failed:
                task.reset_progress()
                task.status = TaskStatus.WAITING
                if self._is_running and self._executor:
                    self._submit_task(task, download_func)

            logger.info(f"重试 {len(failed)} 个失败任务")
            return len(failed)

    # ========== 内部方法 ==========

    def _submit_task(
        self,
        task: DownloadTask,
        download_func: Callable[[DownloadTask], bool],
    ) -> None:
        """提交任务到线程池执行

        Args:
            task: 下载任务
            download_func: 实际下载函数
        """
        if self._executor is None:
            return

        future = self._executor.submit(self._execute_task, task, download_func)
        self._futures[task.task_id] = future

    def _execute_task(
        self,
        task: DownloadTask,
        download_func: Callable[[DownloadTask], bool],
    ) -> None:
        """在线程池中执行单个下载任务

        Args:
            task: 下载任务
            download_func: 实际下载函数
        """
        task.status = TaskStatus.DOWNLOADING

        if self._on_task_started:
            self._on_task_started(task)

        try:
            success = download_func(task)

            if task.status == TaskStatus.CANCELLED:
                if self._on_task_failed:
                    self._on_task_failed(task)
            elif success:
                task.status = TaskStatus.COMPLETED
                if self._on_task_completed:
                    self._on_task_completed(task)
            else:
                task.status = TaskStatus.FAILED
                if self._on_task_failed:
                    self._on_task_failed(task)

        except Exception as e:
            logger.error(f"任务执行异常 {task.task_id}: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)[:500]
            if self._on_task_failed:
                self._on_task_failed(task)

    def _monitor_completion(self) -> None:
        """监控所有任务是否完成"""
        while self._is_running:
            time.sleep(1)

            with self._lock:
                if not self._tasks:
                    continue

                # 检查是否所有任务都已完成（不是等待中或下载中）
                active_statuses = {
                    TaskStatus.WAITING,
                    TaskStatus.DOWNLOADING,
                    TaskStatus.MERGING,
                    TaskStatus.PAUSED,
                }
                has_active = any(
                    t.status in active_statuses
                    for t in self._tasks.values()
                )

                if not has_active:
                    self._is_running = False
                    if self._executor:
                        self._executor.shutdown(wait=False)
                        self._executor = None
                    if self._on_all_completed:
                        self._on_all_completed()
                    break

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取指定任务

        Args:
            task_id: 任务 ID

        Returns:
            DownloadTask 或 None
        """
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        return list(self._tasks.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[DownloadTask]:
        """按状态获取任务

        Args:
            status: 任务状态

        Returns:
            符合条件的任务列表
        """
        return [t for t in self._tasks.values() if t.status == status]
