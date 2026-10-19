from daily_texts.domain.church_year import church_day_label_en, church_day_label_zh


def test_trinity_sunday_matches_the_pentecost_count() -> None:
    assert church_day_label_zh("20. Sonntag nach Trinitatis") == "聖靈降臨後第二十一個主日"
    assert church_day_label_zh("19. Sonntag nach Trinitatis") == "聖靈降臨後第二十個主日"


def test_named_feasts_and_advent() -> None:
    assert church_day_label_zh("Erntedankfest") == "收穫感恩節"
    assert church_day_label_zh("1. Sonntag im Advent") == "將臨期第一主日"
    assert church_day_label_zh("1. Sonntag nach Weihnachten") == "聖誕後第一主日"
    assert (
        church_day_label_zh("Letzter Sonntag des Kirchenjahres – Ewigkeitssonntag")
        == "教會年最後主日（永生主日）"
    )


def test_blank_church_day_adds_nothing() -> None:
    assert church_day_label_zh("") == ""
    assert church_day_label_zh("   ") == ""
    assert church_day_label_en("") == ""


def test_english_labels_use_the_pentecost_count() -> None:
    assert (
        church_day_label_en("20. Sonntag nach Trinitatis")
        == "Twenty-first Sunday after Pentecost"
    )
    assert church_day_label_en("1. Sonntag im Advent") == "First Sunday of Advent"
    assert church_day_label_en("Erntedankfest") == "Harvest Thanksgiving"
