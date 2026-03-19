import random
from uuid import uuid4

from locust import HttpUser, between, task


class ShortLinksUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self) -> None:
        self.created_codes: list[str] = []
        self.original_url = "https://example.com/load-test"

    @task(4)
    def create_link(self) -> None:
        alias = f"load-{uuid4().hex[:10]}"
        response = self.client.post(
            "/links/shorten",
            json={
                "original_url": self.original_url,
                "custom_alias": alias,
            },
            name="/links/shorten",
        )
        if response.status_code == 201:
            self.created_codes.append(response.json()["short_code"])

    @task(3)
    def search_links(self) -> None:
        self.client.get(
            "/links/search",
            params={"original_url": self.original_url},
            name="/links/search",
        )

    @task(2)
    def get_stats(self) -> None:
        if not self.created_codes:
            return
        short_code = random.choice(self.created_codes)
        self.client.get(f"/links/{short_code}/stats", name="/links/{short_code}/stats")

    @task(1)
    def follow_short_link(self) -> None:
        if not self.created_codes:
            return
        short_code = random.choice(self.created_codes)
        self.client.get(
            f"/links/{short_code}",
            name="/links/{short_code}",
            allow_redirects=False,
        )
