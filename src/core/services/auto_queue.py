from core import lcu
class AutoQueueService:
    def __init__(self):
        self.client = lcu.get_client()
        self.is_running = False

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.client.create_lobby()
        self.client.start_matchmaking(queue_id=420)  # 420 是召唤师峡谷的队列ID

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        # 停止自动排队逻辑，清理资源等
        self.client.game_flow.decline_ready_check()