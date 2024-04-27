import queue
from datetime import datetime
from threading import Thread

from sqlalchemy import Engine, insert
from sqlalchemy.orm import sessionmaker

from model import Log


class Logger:
    log_queue = queue.Queue()
    log_thread = None

    def __init__(self, db: Engine):
        self.db = db
        self.log_thread = LogThread(db, Logger.log_queue)
        self.log_thread.start()

    def add_log(self, log_type: str, content: str, request=None, user=None):
        """
        Add log
        :param user: User
        :param request: Request
        :param log_type: Log type
        :param content: Log content
        :return: None
        """
        user = request.ctx.user if request and hasattr(request.ctx, "user") else user

        request_ip = request.remote_addr or request.headers.get("X-Real-IP")
        if not request_ip:
            request_ip = request.headers.get("X-Forwarded-For")
            if request_ip:
                request_ip = request_ip.split(",")[0]
            else:
                request_ip = request.ip or "Unknown IP"

        log = Log(
            user_id=user.id,
            log_type=log_type,
            content=content,
            user_name=user.name,
            user_employee_id=user.employee_id,
            user_type=user.user_type,
            operation_time=datetime.now(),
            operation_ip=request_ip,
        )

        self.log_queue.put(log)


class LogThread(Thread):
    log_queue: queue.Queue

    def __init__(self, db: Engine, log_queue):
        super().__init__()
        self.session_factory = sessionmaker(bind=db)
        self.log_queue = log_queue

    def run(self):
        while True:
            log = Logger.log_queue.get()
            if log is None:
                break

            with self.session_factory() as session:
                session.add(log)
                session.commit()
                Logger.log_queue.task_done()
