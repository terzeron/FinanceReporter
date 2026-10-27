See @AGENTS.md

# CodeGraph — Code Intelligence

이 프로젝트의 그래프 탐색은 CodeGraph로 한다. 인덱스는 `.codegraph/`에 있고,
MCP 서버(`codegraph serve --mcp`)가 파일 변경을 감지해 자동 동기화한다.
`.codegraph/`가 없으면 프로젝트 루트에서 `codegraph init`을 한 번 실행한다.

## Always Do

- 함수·메서드를 고치기 전에 호출자와 영향 범위를 확인한다.
  MCP `codegraph_explore`/caller/impact 도구, 또는 CLI
  `codegraph callers <심볼>`, `codegraph impact <심볼> -d <깊이>`를 쓴다.
- 정방향 추적은 `codegraph callees <심볼>`로 한다.
- 커밋 전 변경 범위는 `git status`와 `git diff --stat`으로 확인한다.
- 결과가 0건이거나 경로가 끊기면 텍스트 검색으로 확인한다.
  클로저·동적 디스패치·콜백을 거치는 호출은 놓칠 수 있다.

## Never Do

- 0건 결과를 "사용처 없음"의 증거로 삼지 않는다.
- GitNexus 도구를 쓰지 않는다. GitNexus는 설치와 인덱스를 모두 제거했다.
