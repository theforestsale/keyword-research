import pytest
from services.ai_researcher import (
    parse_response,
    build_prompt,
    AIResearchError,
)


def test_parse_response_valid():
    raw = (
        '{"keywords": ['
        '{"keyword": "coffee beans", "volume_est": 1000, "difficulty_est": 25, "intent": "informational", "cpc_est": 1.2},'
        '{"keyword": "buy coffee online", "volume_est": 500, "difficulty_est": 40, "intent": "transactional", "cpc_est": 2.0}'
        "]}"
    )
    result = parse_response(raw, 10)
    assert len(result) == 2
    assert result[0]["keyword"] == "coffee beans"
    assert result[0]["volume_est"] == 1000
    assert result[0]["difficulty_est"] == 25
    assert result[0]["intent"] == "informational"
    assert result[0]["cpc_est"] == 1.2


def test_parse_response_invalid_json():
    with pytest.raises(AIResearchError):
        parse_response("not json", 10)


def test_parse_response_missing_keywords():
    with pytest.raises(AIResearchError):
        parse_response("{}", 10)


def test_parse_response_no_usable():
    raw = '{"keywords": [{"foo": "bar"}, {"keyword": ""}]}'
    with pytest.raises(AIResearchError):
        parse_response(raw, 10)


def test_parse_response_respects_max_count():
    raw = '{"keywords": [' + ",".join(
        '{"keyword": "k%d", "volume_est": %d, "difficulty_est": 1, "intent": "x", "cpc_est": 1.0}' % (i, i)
        for i in range(20)
    ) + "]}"
    result = parse_response(raw, 5)
    assert len(result) == 5


def test_build_prompt_with_intent():
    system, user = build_prompt("coffee", 10, "commercial")
    assert "coffee" in user
    assert "commercial" in user


def test_build_prompt_all_intent():
    system, user = build_prompt("coffee", 10, "all")
    assert "Only include keywords" not in user
