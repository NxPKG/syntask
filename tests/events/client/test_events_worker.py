import uuid

import pytest

from syntask import flow
from syntask.client.schemas.objects import State
from syntask.events import Event
from syntask.events.clients import (
    AssertingEventsClient,
    SyntaskEventsClient,
)
from syntask.events.worker import EventsWorker
from syntask.settings import (
    SYNTASK_API_URL,
    temporary_settings,
)


@pytest.fixture
def event() -> Event:
    return Event(
        event="vogon.poetry.read",
        resource={"syntask.resource.id": f"poem.{uuid.uuid4()}"},
    )


def test_emits_event_via_client(asserting_events_worker: EventsWorker, event: Event):
    asserting_events_worker.send(event)

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert asserting_events_worker._client.events == [event]


def test_worker_instance_server_client_non_cloud_api_url():
    with temporary_settings(updates={SYNTASK_API_URL: "http://localhost:8080/api"}):
        worker = EventsWorker.instance()
        assert worker.client_type == SyntaskEventsClient


def test_worker_instance_client_non_cloud_api_url_events_enabled():
    with temporary_settings(updates={SYNTASK_API_URL: "http://localhost:8080/api"}):
        worker = EventsWorker.instance()
        assert worker.client_type == SyntaskEventsClient


def test_worker_instance_ephemeral_syntask_events_client(enable_ephemeral_server):
    """
    Getting an instance of the worker with ephemeral server mode enabled should
    return a SyntaskEventsClient pointing to the subprocess server.
    """
    worker = EventsWorker.instance()
    assert worker.client_type == SyntaskEventsClient


async def test_includes_related_resources_from_run_context(
    asserting_events_worker: EventsWorker, reset_worker_events, syntask_client
):
    @flow
    def emitting_flow():
        from syntask.events import emit_event

        emit_event(
            event="vogon.poetry.read",
            resource={"syntask.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
        )

    state: State[None] = emitting_flow(return_state=True)

    flow_run = await syntask_client.read_flow_run(state.state_details.flow_run_id)
    db_flow = await syntask_client.read_flow(flow_run.flow_id)

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "vogon.poetry.read"
    assert event.resource.id == "vogon.poem.oh-freddled-gruntbuggly"

    assert len(event.related) == 2

    assert event.related[0].id == f"syntask.flow-run.{flow_run.id}"
    assert event.related[0].role == "flow-run"
    assert event.related[0]["syntask.resource.name"] == flow_run.name

    assert event.related[1].id == f"syntask.flow.{db_flow.id}"
    assert event.related[1].role == "flow"
    assert event.related[1]["syntask.resource.name"] == db_flow.name
