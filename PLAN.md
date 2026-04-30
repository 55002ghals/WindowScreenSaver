# Windows 창 배치 저장/복구 프로그램 (WinLayoutSaver)

## Context

Windows에서 Chrome, 에디터, 파일 탐색기 등을 여러 화면에 배치해 작업하다가 재부팅하면 모든 창 위치가 초기화된다. 매번 다시 창을 띄우고 배치하는 수고를 없애기 위해, **현재 창 배치를 "Screen1, Screen2..."로 저장**하고 원클릭 또는 부팅 시 자동으로 복구하는 Windows 데스크톱 프로그램을 만든다.

**핵심 기능 3가지**
1. 현재 화면 배치 저장 (Screen1, Screen2, ...)
2. 원클릭 수동 복구
3. **Auto-rollback: 지정한 레이아웃을 부팅 후 자동 복구 (이게 핵심)**

## Decisions (사용자 확정)

| 항목 | 결정 |
|---|---|
| 언어/스택 | Python 3.11+ + Tkinter (GUI), pywin32 (Windows API) |
| 저장 레이아웃의 앱이 꺼져있을 때 | 저장된 `.exe` 경로 + 인자로 자동 실행 후, 창이 뜨면 배치 |
| 부팅 시 트리거 | Windows Task Scheduler (`At log on` + 지연 N초) |
| 창 매칭 기준 | `exe 경로` + `창 제목 부분 일치/패턴` |

## 프로젝트 구조

```
proj_WindowsContext/
├── README.md
├── requirements.txt         # pywin32, psutil, pillow(옵션)
├── PLAN.md                  # 본 플랜의 사용자용 사본
├── main.py                  # GUI 진입점
├── src/
│   ├── __init__.py
│   ├── capture.py           # 현재 창 열거 + 메타데이터 수집
│   ├── restore.py           # 저장된 레이아웃 → 창 매칭 → 재배치
│   ├── launcher.py          # 꺼진 앱 실행 후 창 대기
│   ├── storage.py           # %APPDATA%\WinLayoutSaver 에 JSON I/O
│   ├── monitors.py          # 모니터 열거/매핑
│   ├── scheduler.py         # Task Scheduler 등록/해제 (schtasks CLI)
│   ├── winapi.py            # pywin32/ctypes 래퍼 모음
│   ├── logging_setup.py     # 파일+콘솔+GUI 큐 핸들러 설정
│   └── gui.py               # Tkinter UI (하단 로그 테일 포함)
├── cli/
│   └── rollback.py          # Task Scheduler가 실행하는 헤드리스 엔트리
└── tests/
    ├── test_capture.py
    ├── test_storage.py
    ├── test_restore_matching.py
    └── test_monitors_compare.py
```

저장소 위치: `%APPDATA%\WinLayoutSaver\`
- `layouts\Screen1.json`, `Screen2.json`, ...
- `config.json` (auto-rollback 설정)
- `logs\app-YYYYMMDD.log` (GUI/일반 실행, RotatingFileHandler 5MB×5)
- `logs\rollback-YYYYMMDD-HHMMSS.log` (헤드리스 rollback 1회 실행분, 별도 파일로 분리해 부팅 복구 결과 추적 용이)

## 데이터 스키마

**`layouts/<name>.json`**
```json
{
  "name": "Screen1",
  "created_at": "2026-04-24T15:30:00+09:00",
  "monitors": [
    {"index": 0, "rect": [0,0,2560,1440], "primary": true, "scale": 1.0},
    {"index": 1, "rect": [2560,0,1920,1080], "primary": false, "scale": 1.0}
  ],
  "windows": [
    {
      "exe_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "exe_args": "--profile-directory=Default",
      "cwd": "C:\\Users\\ab550",
      "title_snapshot": "프로젝트 문서 - Google Chrome",
      "title_pattern": "Chrome$",
      "class_name": "Chrome_WidgetWin_1",
      "placement": {
        "state": "normal",                  // normal | minimized | maximized
        "normal_rect": [100, 100, 1400, 900],
        "min_pos": [-1,-1],
        "max_pos": [-1,-1]
      },
      "monitor_index": 0,
      "z_order": 0,                         // 복원 시 뒤→앞 순서로
      "is_topmost": false
    }
  ]
}
```

**`config.json`**
```json
{
  "auto_rollback": {
    "enabled": true,
    "layout_name": "Screen1",
    "startup_delay_seconds": 20,
    "app_launch_timeout_seconds": 60,
    "per_window_retry_ms": 500
  }
}
```

## 컴포넌트 상세

### 1) `capture.py` — 현재 창 열거
- `win32gui.EnumWindows(cb, None)` 로 top-level 창 순회
- 필터: `IsWindowVisible` + 비어있지 않은 제목 + `WS_EX_TOOLWINDOW` 제외 + cloaked 창 제외 (DWMWA_CLOAKED 체크)
- 각 창에서 수집:
  - `GetWindowText`, `GetClassName`
  - `GetWindowPlacement` (상태 + normal rect)
  - `GetWindowThreadProcessId` → `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` → `QueryFullProcessImageNameW`
  - `MonitorFromWindow` → 모니터 index 매핑
  - Z-order: `GetWindow(hwnd, GW_HWNDNEXT)` 체인 순회로 산출
- **UWP 앱 특수 처리**: 호스트 프로세스가 `ApplicationFrameHost.exe`면 자식 창(child HWND)을 추적해 실제 AppUserModelID/패키지 실행 파일 찾기. 첫 버전에서는 `ApplicationFrameHost`로 저장하고 AUMID 함께 보관 → 실행은 `explorer.exe shell:AppsFolder\<AUMID>` 로.

### 2) `launcher.py` — 꺼진 앱 실행
- 복원 시작 시 저장된 각 window의 `exe_path`가 현재 running 프로세스에 있는지 확인 (psutil)
- 없으면 `subprocess.Popen([exe_path, *exe_args], cwd=cwd, shell=False)` 로 실행
- 실행 직후 poll loop: `per_window_retry_ms` 마다 `EnumWindows` 재호출하여 `(exe_path 일치) AND (title_pattern regex 매치)` 창이 뜰 때까지 최대 `app_launch_timeout_seconds` 대기
- 타임아웃 시 로그 남기고 해당 창은 skip (전체 복원은 계속)

### 3) `restore.py` — 매칭 + 재배치

#### 복원 전 모니터 구성 게이트 (수동·자동 동일 적용)
1. `monitors.compare_monitors(saved, current)` 호출해 `MatchResult` 판정
2. 결과별 복원 대상 필터:
   - `MATCH` → 저장된 모든 window 복원 시도
   - `PRIMARY_ONLY` or `NO_MATCH` → **저장 시 primary 모니터에 있었던 window만** 복원 대상 (`saved_window.monitor_index == saved primary index` 인 것들). 외부 모니터에 있던 window는 launcher도 돌리지 않고 skip. 로그로 "filtered N windows (external monitor absent/changed)" 명시
   - `NO_MATCH` 의 경우 primary rect도 다르므로 primary 창의 좌표가 현재 primary 바깥이면 primary rect 내부로 클램프 (원본 크기 유지, 위치만 보정)
3. 수동 복원 시 `PRIMARY_ONLY`/`NO_MATCH` 이면 GUI 쪽에서 확인 다이얼로그(`"외부 모니터 구성이 달라 주 모니터 창만 복원됩니다. 계속하시겠습니까?"`) 후 진행. 자동 rollback은 확인 없이 정책대로 진행하고 로그만 상세히 남김.

#### 창 매칭 스코어링 (필터 통과한 창들 대상)
- 모든 실행 중 창 수집 후, 저장된 각 window에 대해 스코어링:
  - exe_path 완전 일치: +10
  - title regex 매치: +5
  - class_name 일치: +3
  - 이미 다른 저장 window에 할당된 창: -100 (중복 방지)
- 최고 점수 창 선택. 점수 0 이하면 "매칭 실패"

#### 배치 적용
- 적용 순서: **z_order 역순(뒤 창부터)** 로 처리해 최종 z-order가 맞도록 함
- minimized/maximized: `SetWindowPlacement` 로 상태 + normal_rect 동시 설정
- normal: `SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_NOACTIVATE)` 후 필요시 `ShowWindow(SW_SHOW)`
- **DPI 주의**: 프로세스를 Per-Monitor V2 DPI-aware로 선언 (`SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)`). 좌표는 물리 픽셀 기준으로 저장/복원.

### 4) `monitors.py` — 모니터 해석 + 구성 일치 판정

#### 현재 모니터 열거
- `EnumDisplayMonitors` + `GetMonitorInfoW` 로 현재 모니터 리스트 수집
- 각 모니터: `{index, rect (x,y,w,h), primary, scale}` — rect는 가상 데스크톱 좌표계

#### 저장 시 스냅샷
- `capture` 에서 Screen 저장 시 현재 모든 모니터를 `layouts/<name>.json` 의 `monitors` 필드에 그대로 기록 (이미 데이터 스키마에 포함됨)
- 즉, **외부 모니터 연결 상태를 같이 저장** — 저장 당시 모니터 개수, 각각의 해상도·위치·primary 여부 모두 보존

#### 실시간 일치 판정: `compare_monitors(saved, current) -> MatchResult`
판정 로직:
1. **Primary 일치 여부**: 저장본의 primary 모니터 rect == 현재의 primary 모니터 rect 인가? (해상도·가상 위치·스케일 모두)
2. **External 모니터 일치 여부**: 저장본의 비-primary 모니터 집합 == 현재의 비-primary 모니터 집합 인가?
   - 집합 비교 기준: rect 튜플 정렬 후 완전 일치
3. 반환:
   - `MATCH` — 1과 2 모두 true
   - `PRIMARY_ONLY` — 1은 true, 2가 false (외부 모니터 구성이 달라짐: 연결/해제/해상도 변경)
   - `NO_MATCH` — 1이 false (primary 자체가 다름: 해상도 변경, 모니터 교체 등)

#### 실시간 감시
- GUI 쪽에서 `WM_DISPLAYCHANGE` 메시지 수신 or 1초 간격 폴링으로 현재 구성 변화 감지
- 변화 감지 시 GUI 상단 "Current monitors" 스트립 갱신 + 각 Screen 행의 match 표시(✓/⚠) 재계산

### 5) `scheduler.py` — Task Scheduler 등록
- GUI에서 Auto-rollback ON → `schtasks.exe /Create /TN "WinLayoutSaver_Rollback" /TR "\"pythonw.exe\" \"...\\cli\\rollback.py\"" /SC ONLOGON /DELAY 0000:20 /RL LIMITED /F` (delay 값은 `config.json` 에서 읽어 동적으로 조립)
- 해제 시: `/Delete /F`
- **관리자 권한 불필요** (`/RL LIMITED`, 사용자 로그온 스코프). 실행되는 프로세스 권한으로 창을 이동하므로 admin 창은 움직일 수 없다는 한계 문서화.
- pyinstaller 패키징 시 `.exe`를 직접 등록하도록 경로 전환

### 6) `cli/rollback.py` — 헤드리스 복원 엔트리
- 인자 없이 실행, `config.json` 읽어 대상 레이아웃 로드 → launcher → restore 순서로 실행
- 모든 단계 파일 로그 (`logs/rollback-*.log`)
- 시작 지연은 Task Scheduler `/DELAY` 에 맡기고 본 스크립트에서는 별도 sleep 없음

### 7) `gui.py` — Tkinter UI
```
┌─ WinLayoutSaver ──────────────────────────────────────────┐
│ Current monitors: #0★ 2560x1440  #1 1920x1080 (at 2560,0)  │
│ [ Save Current Layout ]    [ Refresh ]                     │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ ● Screen1 ✓match    [Restore] [설정] [삭제]          │  │
│  │ ○ Screen2 ⚠primary   [Restore] [설정] [삭제]         │  │
│  │ ○ Screen3 ⚠mismatch [Restore] [설정] [삭제]          │  │
│  └─────────────────────────────────────────────────────┘  │
│  Auto-rollback on boot: [Screen1 ▼] [Enable]               │
│  Startup delay: [20] sec                                   │
│                                                            │
│  Status: Last restored Screen1 at 15:32                    │
│                                                            │
│ ─── Logs (tail) ───────────────────────────────────────── │
│ [DEBUG] [INFO] [WARN] [ERROR]  [Clear] [Copy] [OpenDir]   │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ 15:32:04.112 INFO  capture: enumerating windows      │  │
│ │ 15:32:04.128 INFO  capture: found 12 candidates      │  │
│ │ 15:32:04.139 INFO  storage: saved Screen1 (8 w)      │  │
│ │ 15:32:08.221 INFO  restore: match chrome #1 s=15     │  │
│ │ 15:32:08.245 WARN  restore: no match for Notepad     │  │
│ │ ...                                                  │  │
│ └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```
- **상단 "Current monitors" 스트립**: `monitors.list_current()` 결과를 실시간 표시 (primary는 `★`). `WM_DISPLAYCHANGE` or 1초 폴링으로 갱신
- 라디오(●)는 현재 auto-rollback 선택된 레이아웃 표시
- **각 Screen 행의 모니터 일치 마크** (실시간):
  - `✓match` — 저장 당시 모니터 구성과 현재가 완전 일치 → 전체 복원
  - `⚠primary` — primary는 같지만 외부 모니터 구성이 다름 → primary 창만 복원
  - `⚠mismatch` — primary 자체가 다름 → primary 창만 복원 + 좌표 클램프
- [설정]: 레이아웃 이름 변경 + 창 목록 미리보기 (제목/앱/위치/저장시 모니터 index)
- [삭제]: 레이아웃 삭제
- Enable 체크 시 `scheduler.register()`, 해제 시 `scheduler.unregister()`
- **`⚠` 상태에서 Restore 클릭 시 확인 다이얼로그**: "외부 모니터 구성이 달라 주 모니터 창만 복원됩니다. 계속하시겠습니까? [예/아니오]"
- 긴 작업(복원/저장)은 threading으로 UI 블록 방지
- **하단 로그 테일 패널 (임시 디버깅용, v1 포함)** — 아래 "로깅 전략" 참조

## 로깅 전략 (디버깅 편의를 위한 필수 요소)

### 목표
- **코드 흐름을 로그만 봐도 따라갈 수 있도록** 중요한 로직 마일스톤마다 정보 로그 남김
- **파일 로그 + GUI 테일**을 동시에 제공해 개발/QA 중 현상 파악 즉시 가능
- Auto-rollback은 헤드리스 실행이라 파일 로그가 유일한 증거 → 상세하게 기록

### 구현: `src/logging_setup.py`
- Python 표준 `logging` 모듈 사용 (추가 의존성 없음)
- 로그 포맷: `%(asctime)s.%(msecs)03d %(levelname)-5s %(name)-12s: %(message)s`
  - 예: `2026-04-24 15:32:04.112 INFO  capture     : enumerated 12 windows in 16ms`
- 핸들러 3개 동시 부착:
  1. **파일 핸들러** (`RotatingFileHandler`)
     - 경로: `%APPDATA%\WinLayoutSaver\logs\app-YYYYMMDD.log`
     - 회전: 5MB × 5개 파일 보관
     - 레벨: DEBUG (전부 기록)
  2. **콘솔 핸들러** (stderr)
     - 레벨: INFO
     - GUI 없이 CLI 실행 시 확인용
  3. **GUI 테일 핸들러** (커스텀 `QueueHandler`)
     - 메모리 큐에 LogRecord 푸시 → Tkinter `after()` 루프가 100ms마다 큐 drain 후 Text 위젯에 append
     - 레벨: 사용자 선택 (DEBUG/INFO/WARN/ERROR 체크박스)
     - 최대 1,000줄 유지 (초과 시 앞에서 삭제)
- 모듈별 로거: `logging.getLogger("capture")`, `"restore"`, `"launcher"`, `"storage"`, `"scheduler"`, `"monitors"`, `"gui"`, `"rollback"`
- **GUI 초기화 시 또는 `cli/rollback.py` 진입 시 즉시 `setup_logging()` 호출**

### 마일스톤 로그 체크리스트

각 컴포넌트가 **반드시 남겨야 할** 로그. 구현 시 해당 위치에 `logger.info(...)`/`logger.debug(...)` 주입.

| 모듈 | 레벨 | 시점 |
|---|---|---|
| `capture` | INFO | 창 열거 시작/종료 (소요 ms 포함), 최종 수집 창 개수 |
| `capture` | DEBUG | 각 창 1줄 (`hwnd=0x..., pid=..., exe=..., title='...', rect=(x,y,w,h), state=normal`) |
| `capture` | WARN | 제외된 창 이유 (`skipped cloaked`, `skipped no-title`, `OpenProcess failed`) |
| `storage` | INFO | `save_layout(name)` 시작, 저장 완료 (파일 경로 + 창 개수) |
| `storage` | INFO | `load_layout(name)` 로드 완료 (파일 경로 + 창 개수) |
| `storage` | ERROR | JSON 파싱 실패, 파일 쓰기 실패 (파일 경로 + 예외) |
| `launcher` | INFO | 미실행 앱 판정 결과 (`3 of 8 apps not running`) |
| `launcher` | INFO | 앱 실행 시도 (`launching chrome.exe args=[...]`) |
| `launcher` | INFO | 창 등장 성공/실패 (`matched after 2.3s`, `timeout after 60s`) |
| `launcher` | DEBUG | 폴링 루프 틱마다 간단 상태 (너무 많아지지 않게 500ms 간격) |
| `restore` | INFO | 복원 시작 (레이아웃 이름 + 타겟 창 개수) |
| `restore` | INFO | 각 매칭 결과 (`matched saved 'Chrome' → hwnd=0x...  score=15`) |
| `restore` | WARN | 매칭 실패 (`no candidate for 'Notepad' (exe=...)`)  |
| `restore` | INFO | SetWindowPlacement/SetWindowPos 적용 결과 (hwnd + rect + 성공 여부) |
| `restore` | INFO | 복원 요약 (`restored 7/8 windows, 1 failed, elapsed 340ms`) |
| `monitors` | INFO | 열거된 모니터 요약 (`2 monitors: #0 primary 2560x1440, #1 1920x1080`) |
| `monitors` | WARN | 저장 시와 현재 구성 불일치 감지 (어떻게 다른지) |
| `scheduler` | INFO | schtasks 명령 전체 (파라미터 포함) + exit code + stdout 요약 |
| `scheduler` | ERROR | schtasks 실패 (stderr 포함) |
| `rollback` | INFO | 헤드리스 실행 시작 (레이아웃 + delay 정보 + 현재 PID) |
| `rollback` | INFO | 각 단계 경계 (`--- phase: launch missing apps ---`, `--- phase: restore placement ---`) |
| `rollback` | INFO | 전체 종료 (총 소요, 성공/실패 개수) |
| `gui` | INFO | 사용자 조작 주요 이벤트 (Save/Restore/Delete/Enable rollback 버튼 클릭) |

### GUI 로그 테일 세부 사양
- 위치: 메인 창 하단 고정 패널 (크기 조절 가능한 splitter)
- 위젯: `tkinter.scrolledtext.ScrolledText` (읽기 전용, monospace 폰트)
- 타임스탬프: `HH:MM:SS.mmm` (로컬 시간)
- 레벨별 색상 태깅:
  - DEBUG: 회색, INFO: 기본, WARN: 주황, ERROR: 빨강
- 필터 체크박스: 각 레벨 on/off 즉시 반영 (현재 버퍼 필터링, 새 로그는 기준에 맞게 표시)
- 버튼:
  - `Clear`: 화면 버퍼만 비움 (파일 로그는 유지)
  - `Copy`: 현재 보이는 텍스트 전체 클립보드 복사
  - `Open log folder`: `os.startfile(logs_dir)` 로 탐색기 오픈
- 자동 스크롤: 사용자가 마지막 줄에 있으면 새 로그 시 자동 스크롤, 위로 올려둔 상태면 자동 스크롤 중지 (UX)
- 성능: 로그 폭주 방지를 위해 큐에서 한 번에 최대 200개만 drain

### 의존성 영향
- 추가 Python 패키지 없음 (`logging`은 표준 라이브러리)

## 의존성

`requirements.txt`
```
pywin32>=306
psutil>=5.9
```
- Tkinter는 Python 표준 라이브러리
- 로깅은 Python 표준 `logging` 사용 (추가 의존성 없음)

`requirements-dev.txt` (개발/테스트)
```
pytest>=8.0
pytest-mock>=3.12
coverage>=7.4
```

## 구현 단계 (단계마다 체크포인트)

1. **[Stage 1] logging_setup + capture + storage 뼈대**
   - `logging_setup.setup_logging(enable_gui_handler=False)` 부터 먼저 구현 (파일+콘솔만)
   - `capture.list_current_windows()` 가 현재 창 JSON을 stdout에 출력 + 마일스톤 로그
   - `storage.save_layout("Screen1")` / `load_layout` / `list_layouts` + 마일스톤 로그
   - 검증: CLI로 저장 → `logs/app-*.log` 파일에 창 열거/저장 흐름이 기록되어 있고 JSON 내용 일치 확인

2. **[Stage 2] restore (running 앱만)**
   - 매칭 스코어링 + SetWindowPlacement/SetWindowPos 적용 + 마일스톤 로그
   - 검증: 창 몇 개 배치 → Screen1 저장 → 창들 흐트러뜨리기 → `python -m cli.rollback --layout Screen1 --no-launch` → 위치 복구 + 로그에 각 창 매칭 점수·적용 rect 기록 확인

3. **[Stage 3] Tkinter GUI + 로그 테일 패널**
   - Save/Restore/List/Delete 핵심 동작
   - **GUI 큐 핸들러 연결**, 하단 테일 패널에 실시간 로그 표시 + 레벨 필터 + Clear/Copy/OpenDir
   - 검증: GUI에서 Save 누르면 테일 패널에 `storage: saved Screen1 (N windows)` 즉시 출력. Restore 시 각 창 매칭·적용 로그가 하나씩 흘러가는 것을 눈으로 확인.

4. **[Stage 4] launcher (꺼진 앱 자동 실행)**
   - psutil로 프로세스 존재 확인, 미존재 시 Popen + 창 폴링
   - 검증: Chrome 종료 상태에서 Restore → Chrome 자동 실행 후 창 배치 확인

5. **[Stage 5] Task Scheduler 통합 + 헤드리스 rollback**
   - `scheduler.register()` / Enable 토글
   - 검증: Auto-rollback ON → **재부팅** → 20초 후 자동 복구 확인 (로그 파일로도 확인)

6. **[Stage 6] 다중 모니터 정책 + DPI + UWP 앱 보강**
   - Per-Monitor V2 awareness 설정
   - `monitors.list_current()` + `compare_monitors()` 구현
   - GUI 상단 실시간 모니터 스트립 + 각 Screen 행 일치 마크(✓/⚠) 렌더링, `WM_DISPLAYCHANGE` or 1초 폴링으로 갱신
   - `restore.py` 복원 전 게이트: MATCH/PRIMARY_ONLY/NO_MATCH 분기 → primary 창만 필터링 + 필요 시 좌표 클램프
   - 수동 복원 시 `⚠` 상태에서 확인 다이얼로그
   - UWP 앱(AUMID 기반) 특수 실행 경로
   - 검증: Verification 5·6·7 (다중 모니터 시나리오 3종)

7. **[Stage 7] 패키징 (선택)**
   - PyInstaller로 단일 `.exe` 생성, Task Scheduler 엔트리도 `.exe` 경로로

## 핵심 제약/한계 (사용자 사전 합의 필요)

- **관리자 권한으로 실행 중인 창**(예: admin으로 실행한 cmd)은 일반 사용자 프로세스에서 이동 불가. v1은 skip + 로그 경고.
- **Chrome 탭/URL은 복원 안 함** — 창 "위치/크기/상태"만. 탭 복원은 Chrome의 기동 옵션/세션 복원 기능에 위임.
- **같은 exe의 여러 창**은 title_pattern으로 구분. title이 완전히 동일한 경우(예: "새 Notepad" 2개) 저장된 z-order에 따라 순차 매칭하지만 완벽히 보장되진 않음.
- **모니터 구성 변경** 정책 (수동·자동 복원 동일):
  - 저장 당시 외부 모니터 연결 상태까지 함께 보존 (`layouts/<name>.json` 의 `monitors` 배열)
  - GUI가 현재 구성을 실시간으로 파악해 각 Screen 행에 `✓match` / `⚠primary` / `⚠mismatch` 표시
  - 구성이 다르면(외부 모니터 추가/제거/해상도 변경) **주 모니터(primary)에 저장되어 있던 창만 복원** — 외부 모니터에 있던 창은 launcher 포함 전체 skip
  - primary 자체가 달라진 경우에도 primary 창만 복원하되 현재 primary rect 내부로 좌표 클램프
  - 수동 복원 시 확인 다이얼로그, 자동 rollback 은 로그만 남기고 정책대로 실행
- **Auto-rollback은 사용자 로그온 1회** — 로그인 중에는 다시 안 걸림. (요구되면 GUI 내 "지금 복구" 버튼으로 대체.)

## Verification (종료 기준)

각 스테이지 완료 시 수동 테스트:

1. **기본 저장/복구**
   - Chrome, Notepad, Explorer 3개 창 서로 다른 위치에 배치
   - Save Current → Screen1 생성 확인
   - 모든 창 다른 위치로 옮기기
   - Restore Screen1 → 원래 위치로 돌아오는지 확인

2. **꺼진 앱 자동 실행**
   - Chrome 종료 상태에서 Restore Screen1
   - Chrome이 자동 실행되고 저장 위치에 창이 뜨는지 확인
   - 로그에 "launched chrome.exe, waited 2.3s, matched window" 흐름 기록 확인

3. **Auto-rollback**
   - Screen1을 auto-rollback 대상으로 enable, delay 20초 (default)
   - 모든 앱 종료 후 **재부팅**
   - 로그인 후 20초 뒤 Chrome/Notepad/Explorer가 자동 실행되고 Screen1 위치로 복구되는지 확인
   - `%APPDATA%\WinLayoutSaver\logs\rollback-*.log` 열어 `--- phase: launch missing apps ---` / `--- phase: restore placement ---` 경계와 각 창 매칭·적용 로그 시퀀스가 남았는지 확인

4. **로그 테일 패널 동작 확인**
   - GUI 실행 중 Save/Restore를 반복하면서 테일 패널에 타임스탬프 + 레벨 색상이 잘 표시되는지
   - 레벨 필터 체크박스 toggle 시 즉시 필터링되는지
   - `Open log folder` 버튼으로 탐색기 열려 파일 로그 위치 접근 가능한지
   - 1,000줄 초과 시 앞줄이 밀려 나가는지 (성능 보호)

5. **다중 모니터 — 구성 일치 시**
   - 2대 모니터에서 각 모니터에 창 1~2개씩 배치하여 Screen1 저장
   - 구성 유지한 채 창 흐트러뜨리고 Restore → **모든 창**이 원 위치로 복구되는지 확인
   - GUI에서 Screen1 옆에 `✓match` 표시되는지 확인

6. **다중 모니터 — 외부 모니터 제거/변경 시**
   - Screen1 은 위와 같이 2대 구성으로 저장되어 있어야 함
   - 외부 모니터 케이블 분리 (또는 Windows 설정에서 해당 디스플레이 비활성)
   - GUI: 상단 "Current monitors" 스트립이 즉시 1대로 갱신되고, Screen1 행이 `⚠primary` 로 바뀌는지 확인
   - Restore Screen1 클릭 → 확인 다이얼로그 노출, "예" 선택 → primary 모니터에 있던 창만 복원되고 외부 모니터에 있던 창은 런처도 돌지 않고 그대로 꺼져 있음을 확인
   - 로그에 `restore: filtered N windows (external monitor absent)` 기록 확인
   - 자동 rollback 시나리오: 외부 모니터 분리 상태로 재부팅 → 확인 다이얼로그 없이 동일 정책이 적용되고 `logs/rollback-*.log` 에 동일 필터 로그가 남는지 확인

7. **다중 모니터 — primary 해상도 변경 시**
   - 2560x1440으로 저장했던 Screen1 을 사용 중, 디스플레이 설정에서 primary를 1920x1080으로 변경
   - Screen1 행이 `⚠mismatch` 로 표시되는지 확인
   - Restore → primary 창만 복원되고, 기존 좌표가 1920x1080 바깥인 창은 새 primary rect 내부로 클램프되어 보이는지 확인

8. **단위 테스트**
   - `tests/test_restore_matching.py`: 매칭 스코어링 로직 (모의 데이터)
   - `tests/test_storage.py`: JSON I/O 라운드트립
   - `tests/test_capture.py`: 창 메타데이터 파싱 (필터 규칙)
   - `tests/test_monitors_compare.py`: `compare_monitors` 로 `MATCH`/`PRIMARY_ONLY`/`NO_MATCH` 3 케이스와 primary 창 필터 함수

## 결정사항 (구 오픈 이슈, 사용자 확정)

- **저장 파일명 자동증가**: "Screen1" 존재 시 "Screen2" 자동 부여. 이후 [설정] 다이얼로그에서 rename 허용.
- **기본 startup_delay**: 20초. GUI의 "Startup delay" 입력으로 조절. 변경 시 `config.json` 갱신 + Task Scheduler 등록 재작성(`/DELAY` 값 반영).
- **Tray icon**: v1은 일반 창만. Tray는 v2 범위로 보류하고, v2 착수 시점에 필요 여부 재확인.
- **한/영 UI**: 한국어 기본, 옵션으로 영어 전환 지원. 문자열은 `src/i18n.py`에 `STRINGS = {"ko": {...}, "en": {...}}` 딕셔너리로 중앙화, GUI는 `t("key")` 로 조회. 언어 설정은 `config.json`의 `"ui": {"language": "ko"}` 에 저장, 설정 변경 시 재시작 없이 라벨 갱신.

## 테스트 전략 (TDD)

**원칙**: 모든 단계는 "실패하는 테스트 → 통과시키는 코드 → 리팩터" 의 Red-Green-Refactor 사이클로 진행한다. 수정이 끝날 때마다 전체 테스트 스위트를 실행해 기능 회귀를 방지한다.

### 프레임워크/도구
- **pytest** (테스트 러너): 간결한 assert, fixture, 파라미터화 지원
- **pytest-mock** (mock 래퍼): Windows API 호출을 모킹해 실제 OS 자원 없이 로직 검증
- **coverage.py**: `pytest --cov=src` 로 커버리지 리포트, 목표 ≥ 80%
- 개발용 의존성은 `requirements-dev.txt` 에 분리 (`pytest`, `pytest-mock`, `coverage`)

### 테스트 계층
1. **단위 테스트 (`tests/`, 대부분)** — Windows API 전부 mock
   - `test_storage.py`: JSON 저장/로드 라운드트립, 스키마 검증, 파일명 자동증가(Screen1 존재 시 Screen2), 손상 파일 처리
   - `test_capture.py`: `EnumWindows`/`GetWindowPlacement` mock → 필터 규칙(cloaked, tool window, 빈 제목 제외) 검증, UWP(ApplicationFrameHost) 분기
   - `test_restore_matching.py`: 스코어링 로직 (exe=+10, title=+5, class=+3, 중복=-100). 모호한 케이스·중복 제목·매칭 실패 케이스 포함
   - `test_monitors_compare.py`: `compare_monitors()` 의 MATCH / PRIMARY_ONLY / NO_MATCH 3분기 + primary 창 필터 함수 + 좌표 클램프 함수
   - `test_launcher.py`: psutil mock으로 프로세스 존재 여부 판정 + 창 등장 폴링 타임아웃
   - `test_scheduler.py`: `schtasks` 호출을 `subprocess.run` mock 으로 받아 인자 문자열 검증 (register/unregister/delay 반영)
   - `test_logging_setup.py`: 핸들러 개수·레벨·포맷 검증, QueueHandler가 메모리 큐에 푸시하는지
   - `test_i18n.py`: 모든 키가 ko/en 양쪽에 존재, 누락 키 fallback
2. **통합 테스트 (`tests/integration/`, 소수, 수동 트리거)**
   - 실제 Windows API 호출을 포함하므로 `pytest -m integration` 로만 실행 (`@pytest.mark.integration`)
   - 현재 프로세스의 창을 열고 `SetWindowPos` 왕복 검증 등
   - CI가 아닌 로컬 수동 실행 전용

### 실행 규칙
- **수정 후 항상 실행**: `pytest -q` (빠른 단위 테스트). 실패 시 즉시 수정.
- **통합 테스트**: Stage 2 이후 기능 변경 시 `pytest -q -m integration` 로 별도 실행.
- **커밋 전**: `pytest --cov=src --cov-report=term-missing` 로 커버리지 확인.
- 각 Stage 의 "검증" 체크포인트는 **대응 테스트가 초록불일 것** + 수동 Verification 시나리오 확인 두 가지를 모두 요구.

### 디렉토리 추가
```
tests/
├── conftest.py              # 공통 fixture (mock win32gui 모듈, 임시 APPDATA 디렉토리)
├── test_storage.py
├── test_capture.py
├── test_restore_matching.py
├── test_monitors_compare.py
├── test_launcher.py
├── test_scheduler.py
├── test_logging_setup.py
├── test_i18n.py
└── integration/
    ├── __init__.py
    └── test_restore_live.py   # @pytest.mark.integration
```

### Stage 별 TDD 흐름 (요약)
- Stage 1: `test_logging_setup.py` → `test_storage.py` → `test_capture.py` 먼저 작성 후 구현
- Stage 2: `test_restore_matching.py` 작성 후 `restore.py` 스코어링 구현
- Stage 3: GUI는 로직만 추출해 단위 테스트 (Tkinter 위젯 자체는 수동 검증)
- Stage 4: `test_launcher.py` (psutil/Popen mock)
- Stage 5: `test_scheduler.py` (subprocess mock)
- Stage 6: `test_monitors_compare.py`
- 모든 Stage 마무리 시 `pytest -q` 전체 그린 필수

