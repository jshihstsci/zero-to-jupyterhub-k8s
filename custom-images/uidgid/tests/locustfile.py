from locust import HttpUser, task


class CheckAlive(HttpUser):
    @task
    def check_alive(self):
        self.client.get("/check-alive")

    @task
    def get_spawn_info(self):
        payload = dict(
            stsci_uuid="12345678-1234-1234-1234-123456789abc",
            stsci_ezid="user_1",
            active_team="team_2",
            teams=["team_1", "team_2"],
        )
        self.client.post("/get-spawn-info", json=payload)
