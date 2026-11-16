"""Shared test setup: a real planting API on an in-memory database, and the assistant wired to it."""

# Pull in the API test database fixture (Lagos, Nairobi, Harare, Hanoi sample rows).
from tests.api.test_api import client as planting_api  # noqa: F401

# Test tools.
import pytest

# Assistant pieces.
from assistant.llm.fake import RuleBasedFakeLLM
# Who is asking.
from assistant.models import Identity
# Builds the assistant.
from assistant.service import build_service
# Assistant settings.
from assistant.settings import Settings


@pytest.fixture()
def settings(tmp_path):
    """Settings that write only into the temporary folder."""
    # Kill file path does not exist, so the assistant is on.
    return Settings(kill_file=str(tmp_path / "off"), review_queue_path=str(tmp_path / "review.jsonl"),
                    api_keys={"adminkey": "admin", "memberkey": "member"})


@pytest.fixture()
def service(planting_api, settings):
    """The assistant talking to the sample API with the offline fake model."""
    # The API test client acts as the web client (it has .get).
    return build_service(settings, http=planting_api, llm=RuleBasedFakeLLM())


@pytest.fixture()
def visitor():
    """An anonymous visitor."""
    # A visitor with no key.
    return Identity("anon-test", "anonymous")
