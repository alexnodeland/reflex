"""Tests for PydanticAI agents."""

from reflex.agent.agents import (
    AlertResponse,
    SummaryResponse,
    alert_agent,
    summary_agent,
)


class TestAlertResponse:
    """Tests for AlertResponse model."""

    def test_alert_response_creation(self) -> None:
        """Test creating an AlertResponse."""
        response = AlertResponse(
            severity="high",
            title="Database Connection Failure",
            description="Multiple database connection timeouts detected.",
            recommended_action="Check database server status and connection pool.",
        )

        assert response.severity == "high"
        assert response.title == "Database Connection Failure"
        assert response.should_notify is True  # Default value

    def test_alert_response_with_no_notify(self) -> None:
        """Test AlertResponse with should_notify disabled."""
        response = AlertResponse(
            severity="low",
            title="Minor issue",
            description="Non-critical issue detected.",
            recommended_action="Monitor for now.",
            should_notify=False,
        )

        assert response.should_notify is False


class TestSummaryResponse:
    """Tests for SummaryResponse model."""

    def test_summary_response_creation(self) -> None:
        """Test creating a SummaryResponse."""
        response = SummaryResponse(
            title="Daily Event Summary",
            highlights=["100 WebSocket events", "5 errors detected"],
            event_count=105,
        )

        assert response.title == "Daily Event Summary"
        assert len(response.highlights) == 2
        assert response.event_count == 105
        assert response.notable_patterns == []  # Default
        assert response.recommendations == []  # Default

    def test_summary_response_with_all_fields(self) -> None:
        """Test SummaryResponse with all optional fields."""
        response = SummaryResponse(
            title="Hourly Summary",
            highlights=["High traffic detected"],
            event_count=500,
            notable_patterns=["Traffic spike at 14:00"],
            recommendations=["Consider scaling up"],
        )

        assert len(response.notable_patterns) == 1
        assert len(response.recommendations) == 1


class TestAlertAgent:
    """Tests for alert_agent configuration."""

    def test_alert_agent_exists(self) -> None:
        """Test alert_agent is properly configured."""
        # Verify agent was created successfully
        assert alert_agent is not None
        # Check it has the correct output type
        assert alert_agent._output_type is AlertResponse  # type: ignore[reportPrivateUsage]

    def test_alert_agent_has_system_prompt(self) -> None:
        """Test alert_agent has a system prompt."""
        # PydanticAI stores system prompts internally
        prompts = alert_agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert prompts is not None
        assert len(prompts) > 0


class TestSummaryAgent:
    """Tests for summary_agent configuration."""

    def test_summary_agent_exists(self) -> None:
        """Test summary_agent is properly configured."""
        # Verify agent was created successfully
        assert summary_agent is not None
        # Check it has the correct output type
        assert summary_agent._output_type is SummaryResponse  # type: ignore[reportPrivateUsage]

    def test_summary_agent_has_system_prompt(self) -> None:
        """Test summary_agent has a system prompt."""
        prompts = summary_agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert prompts is not None
        assert len(prompts) > 0
