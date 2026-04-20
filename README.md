# 회계감사기준 파싱 파이프라인

회계감사기준(ISA) DOCX 문서를 Structured Markdown → JSON → Qdrant 벡터 DB로 변환하는 파이프라인.

## 빠른 시작

```bash
pip install -e ".[dev]"          # 의존성 설치
cp .env.example .env             # API 키 설정
docker compose up -d             # Qdrant 실행 (localhost:6333)
audit-parser convert "raw/0. 회계감사기준 전문(2025 개정).docx" --out output/md/
```

## 문서

- [PLAN.md](./PLAN.md) — 전체 설계 계획 (Phase 0~4, 리스크 매트릭스)
- [CLAUDE.md](./CLAUDE.md) — 개발 컨벤션, 저장소 구조, Agent Teams 실행 지침
