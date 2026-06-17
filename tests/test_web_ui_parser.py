from boss_cli.web_ui.parser import parse_query


def test_parse_full_query():
    result = parse_query("找杭州的 Python 岗位，薪资 20k 以上，3年经验")
    assert "Python" in result["keyword"]
    assert result["city"] == "杭州"
    assert result["salary"] == "20-30K"
    assert result["experience"] == "3-5年"
    assert result["degree"] is None


def test_parse_keyword_only():
    result = parse_query("golang")
    assert result["keyword"] == "golang"
    assert result["city"] is None
    assert result["salary"] is None
    assert result["experience"] is None


def test_parse_with_degree():
    result = parse_query("Java 北京 本科 30k以上")
    assert "Java" in result["keyword"]
    assert result["city"] == "北京"
    assert result["degree"] == "本科"
    assert result["salary"] == "30-50K"


def test_parse_city_not_found_defaults_to_none():
    result = parse_query("Python 火星")
    assert result["keyword"] == "Python 火星"
    assert result["city"] is None


def test_parse_salary_range():
    result = parse_query("15k-20k 前端 上海")
    assert "前端" in result["keyword"]
    assert result["city"] == "上海"
    assert result["salary"] == "15-20K"
