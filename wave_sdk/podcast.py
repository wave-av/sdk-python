"""WAVE SDK - Podcast API. Podcast shows and episodes.

Paths follow the published API operations: ``/v1/podcast/shows`` (``listPodcastShows``,
``createPodcastShow``) and ``/v1/podcast/shows/{showId}/episodes`` (``listPodcastEpisodes``,
``createPodcastEpisode``). The remaining methods (get/update/remove a show, RSS, analytics,
distribution, a single episode) have no published API operation yet and use the same
``/v1/podcast`` prefix.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

from wave_sdk.client import WaveClient

_SHOWS = "/v1/podcast/shows"
_EPISODES = "/v1/podcast/episodes"


def _seg(value: str) -> str:
    return quote(value, safe=":")


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class PodcastShow(BaseModel):
    """``PodcastShow`` from the API reference; unknown fields are kept."""

    model_config = ConfigDict(extra="allow")
    id: str
    name: str | None = None
    description: str | None = None
    coverUrl: str | None = None  # noqa: N815 - wire name
    rssUrl: str | None = None  # noqa: N815 - wire name
    category: str | None = None
    language: str | None = None


class PodcastEpisode(BaseModel):
    """``PodcastEpisode`` from the API reference; unknown fields are kept."""

    model_config = ConfigDict(extra="allow")
    id: str
    showId: str | None = None  # noqa: N815 - wire name
    title: str | None = None
    description: str | None = None
    audioUrl: str | None = None  # noqa: N815 - wire name
    duration: float | None = None
    episodeNumber: int | None = None  # noqa: N815 - wire name


# Names used by earlier releases.
Podcast = PodcastShow
Episode = PodcastEpisode


class PodcastAPI:
    def __init__(self, client: WaveClient):
        self._client = client
        self._base = _SHOWS

    def list(self, **params: Any) -> dict:
        """``GET /v1/podcast/shows`` (paginated: ``page``, ``perPage``)."""
        result: dict = self._client.get(_SHOWS, params=_clean(params))
        return result

    def create(self, name: str, description: str | None = None, category: str | None = None, *, language: str | None = None, explicit: bool | None = None, cover_url: str | None = None, **kwargs: Any) -> PodcastShow:
        """``POST /v1/podcast/shows``."""
        body = {"name": name, "description": description, "category": category, "language": language, "explicit": explicit, "coverUrl": cover_url, **kwargs}
        return PodcastShow(**self._client.post(_SHOWS, json=_clean(body)))

    def list_episodes(self, show_id: str, **params: Any) -> dict:
        """``GET /v1/podcast/shows/{showId}/episodes`` (paginated: ``page``, ``perPage``)."""
        result: dict = self._client.get(f"{_SHOWS}/{_seg(show_id)}/episodes", params=_clean(params))
        return result

    def create_episode(self, show_id: str, title: str, description: str | None = None, *, audio_url: str, episode_number: int | None = None, season_number: int | None = None, published_at: str | None = None, **kwargs: Any) -> PodcastEpisode:
        """``POST /v1/podcast/shows/{showId}/episodes``. ``audio_url`` is required by the API."""
        body = {"title": title, "description": description, "audioUrl": audio_url, "episodeNumber": episode_number, "seasonNumber": season_number, "publishedAt": published_at, **kwargs}
        return PodcastEpisode(**self._client.post(f"{_SHOWS}/{_seg(show_id)}/episodes", json=_clean(body)))

    # No published API operation for the methods below yet.
    def get(self, show_id: str) -> PodcastShow: return PodcastShow(**self._client.get(f"{_SHOWS}/{_seg(show_id)}"))
    def update(self, show_id: str, **kwargs: Any) -> PodcastShow: return PodcastShow(**self._client.patch(f"{_SHOWS}/{_seg(show_id)}", json=kwargs))
    def remove(self, show_id: str) -> None: self._client.delete(f"{_SHOWS}/{_seg(show_id)}")
    def get_episode(self, episode_id: str) -> PodcastEpisode: return PodcastEpisode(**self._client.get(f"{_EPISODES}/{_seg(episode_id)}"))
    def publish_episode(self, episode_id: str) -> PodcastEpisode: return PodcastEpisode(**self._client.post(f"{_EPISODES}/{_seg(episode_id)}/publish"))
    def get_rss_feed(self, show_id: str) -> dict: return self._client.get(f"{_SHOWS}/{_seg(show_id)}/rss")
    def get_analytics(self, show_id: str, **params: Any) -> dict: return self._client.get(f"{_SHOWS}/{_seg(show_id)}/analytics", params=_clean(params))
    def distribute(self, show_id: str, targets: list[str]) -> list[dict]: return self._client.post(f"{_SHOWS}/{_seg(show_id)}/distribute", json={"targets": targets})
