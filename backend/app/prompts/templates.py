TEMPLATES: dict[str, dict] = {
    "kpop": {
        "genre": "K-pop 뮤직비디오",
        "character": "20대 초반 여성 아이돌. 흰 새틴 드레스, 허리까지 내려오는 검은 생머리, 날카로운 눈매",
        "mood": "melancholy, cinematic, emotional",
        "story": "화려한 무대를 마친 아이돌이 빈 무대에 홀로 남아 조명이 꺼지는 순간을 맞이한다",
        "must_have": "마지막 조명이 꺼지는 장면",
        "extra": "첫 컷은 군중 속 클로즈업으로 시작, 마지막은 빈 무대 와이드샷으로 마무리",
    },
    "anime": {
        "genre": "애니메이션 액션",
        "character": "17세 남성 주인공. 검은 후드티, 은발 단발머리, 왼손에 파란 불꽃 문신",
        "mood": "tense, energetic, dramatic",
        "story": "주인공이 거대한 적 앞에서 처음으로 자신의 능력을 완전히 해방시키는 순간",
        "must_have": "파란 불꽃이 폭발적으로 퍼지는 장면",
        "extra": "초반은 슬로우모션, 클라이맥스에서 빠른 컷 전환",
    },
    "game": {
        "genre": "게임 시네마틱 트레일러",
        "character": "중세 기사. 검은 풀플레이트 아머, 붉은 망토, 두 손에 대검. 얼굴은 헬멧으로 가려짐",
        "mood": "epic, dark, heroic",
        "story": "혼자 남은 기사가 불타는 왕국을 배경으로 수천의 적군을 향해 홀로 걸어 나간다",
        "must_have": "불타는 성과 기사의 실루엣이 대비되는 장면",
        "extra": "광각 구도를 많이 활용, 마지막 컷은 오버헤드 뷰",
    },
}


def get_template(genre: str) -> dict:
    """장르 키워드로 가장 가까운 템플릿 반환. 매칭 없으면 kpop 반환."""
    genre_lower = genre.lower()
    if any(k in genre_lower for k in ["kpop", "k-pop", "아이돌", "뮤직비디오"]):
        return TEMPLATES["kpop"]
    if any(k in genre_lower for k in ["anime", "애니", "애니메이션", "액션"]):
        return TEMPLATES["anime"]
    if any(k in genre_lower for k in ["game", "게임", "시네마틱"]):
        return TEMPLATES["game"]
    return TEMPLATES["kpop"]
