<!-- ============ HERO ============ -->
<p align="center">
  <img src="docs/assets/logo.png" width="128" alt="WinLayoutSaver logo" />
</p>

<h1 align="center">WinLayoutSaver</h1>

<p align="center">
  <b>Save and restore your Windows window layouts across multiple monitors — in one click.</b>
  <br/>
  <sub>멀티 모니터 창 배치를 한 번에 저장하고 복원하는 Windows 데스크톱 앱</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Windows 10/11" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/github/v/release/55002ghals/WindowScreenSaver?style=flat-square" alt="Release" />
  <img src="https://img.shields.io/github/license/55002ghals/WindowScreenSaver?style=flat-square" alt="License" />
  <img src="https://img.shields.io/github/downloads/55002ghals/WindowScreenSaver/total?style=flat-square" alt="Downloads" />
</p>

<p align="center">
  <a href="#-installation">Install</a> ·
  <a href="#-features">Features</a> ·
  <a href="#-usage">Usage</a> ·
  <a href="#%EF%B8%8F-build-from-source">Build</a>
</p>

---

## 🤔 Why WinLayoutSaver?

매일 같은 듀얼·트리플 모니터에 같은 창 배치를 다시 만드는 게 지겨우셨나요?
**WinLayoutSaver** 는 모든 보이는 창의 위치·크기·상태를 JSON 으로 저장했다가
한 번의 클릭(또는 로그온 시 자동)으로 그대로 복원합니다.
닫혀 있던 앱은 **다시 실행시키면서** 원래 자리에 배치합니다.

> [!NOTE]
> 별도 관리자 권한이 필요 없습니다. 자동 복원은 Windows 작업 스케줄러를 사용자 권한으로 등록합니다.

---

## ✨ Features

| | |
|---|---|
| 🖼️ **Multi-monitor + DPI aware** | per-monitor DPI 스케일을 정확히 처리 |
| 🗂️ **Virtual Desktop 지원** | 가상 데스크톱 단위로 창 캡처 |
| 🚀 **Full / Quick 복원** | Full = 닫힌 앱 재실행 + 배치 / Quick = 위치만 |
| ⏰ **로그온 자동 복원** | 작업 스케줄러 등록, 시작 지연 설정 가능 |
| 📸 **레이아웃 미리보기** | 저장 시점의 PNG 스냅샷 자동 생성 |
| 🌐 **한국어 / English UI** | 시스템 언어에 따라 자동 전환 |
| 🔍 **모니터 변경 감지** | 모니터 구성이 바뀌면 색상으로 경고 |
| 💾 **사용자 데이터 보존** | `%APPDATA%\WinLayoutSaver\` — 업그레이드·재설치 시에도 유지 |

---

## 📦 Installation

**Recommended — installer:**

1. [Releases](https://github.com/55002ghals/WindowScreenSaver/releases) 에서 `WinLayoutSaverSetup.exe` 다운로드
2. 실행 — 관리자 권한 필요 없음 (`%LOCALAPPDATA%\Programs\WinLayoutSaver` 에 사용자 단위 설치)
3. 시작 메뉴에서 **WinLayoutSaver** 실행

설치 후 두 개의 실행 파일이 들어갑니다:

| 파일 | 용도 |
|---|---|
| `WinLayoutSaver.exe` | 메인 GUI — 이걸 실행하세요 |
| `WinLayoutSaverRollback.exe` | 작업 스케줄러용 헤드리스 복원 — 직접 실행하지 마세요 |

> [!TIP]
> 사용자 데이터(저장된 레이아웃·스크린샷·설정·로그)는 `%APPDATA%\WinLayoutSaver\` 에 저장되며, 업그레이드/제거 시에도 유지됩니다.

---

## 🚀 Usage

### 레이아웃 저장
원하는 창 배치를 만든 후 **현재 배치 저장 / Save Current Layout** 클릭. `Screen<N>` 행이 추가되고 가상 데스크톱 PNG 가 자동 캡처됩니다.

### 복원
목록에서 행을 선택하고 **복원 / Restore** 클릭.
- **Full**: 닫힌 앱을 다시 실행하면서 위치 적용
- **Quick**: 이미 열려 있는 창만 재배치 (빠름)

모니터 구성이 바뀌었으면 행에 `⚠Not matched`(주황) 또는 `⚠mismatch`(빨강) 표시가 뜹니다 — 복원은 동작하지만 창이 의도하지 않은 화면에 갈 수 있습니다.

### 로그온 시 자동 복원

**부팅 자동 복구 / Auto-restore on boot** 섹션에서:

1. 드롭다운에서 레이아웃 선택
2. 모드 선택 (**Quick** / **Full**)
3. 시작 지연 시간 설정 (로그온 후 N 초)
4. **활성화 / Enable** 클릭

사용자 권한의 Windows 작업 스케줄러 항목으로 등록됩니다. 다시 클릭하면 해제.

---

## 🛠️ Build from source

요구 사항: Windows 10/11, Python 3.11+. PyInstaller / Inno Setup 은 `build.bat` 가 winget 으로 자동 설치합니다.

```cmd
git clone https://github.com/55002ghals/WindowScreenSaver.git
cd WindowScreenSaver
build.bat
```

산출물:
- `dist\WinLayoutSaver\` — 실행 가능한 번들
- `installer\Output\WinLayoutSaverSetup.exe` — 배포용 인스톨러

### 개발 환경에서 실행

```cmd
install.bat        :: Python 의존성 설치
python main.py     :: GUI 실행
```

### 수동 빌드

```cmd
pip install -r requirements.txt
pyinstaller WinLayoutSaver.spec --noconfirm
ISCC.exe /DMyAppVersion=1.12.0 installer\WinLayoutSaver.iss
```

---

## 📁 Project layout

<details>
<summary>Click to expand</summary>

```
.
├── main.py                    GUI 진입점
├── cli/rollback.py            헤드리스 복원 (작업 스케줄러 타깃)
├── src/
│   ├── gui.py                 Tkinter UI
│   ├── capture.py             창 열거 + 가상 데스크톱 PNG
│   ├── restore.py             재배치 / 재실행 로직
│   ├── monitors.py            DPI + 멀티 모니터 좌표
│   ├── storage.py             JSON 레이아웃 I/O
│   ├── scheduler.py           Windows 작업 스케줄러 래퍼
│   ├── i18n.py                한/영 문자열
│   └── ...
├── WinLayoutSaver.spec        PyInstaller 설정 (exe 2개 빌드)
├── installer/WinLayoutSaver.iss   Inno Setup 인스톨러 스크립트
├── build.bat                  엔드투엔드 빌드 오케스트레이터
└── requirements.txt
```

</details>

---

## 🧰 Tech stack

Python 3.11+ · tkinter · pywin32 · psutil · Pillow · PyInstaller · Inno Setup

## 🤝 Contributing

Issue / PR 환영합니다.

## 📜 License

[MIT](LICENSE)

<p align="center"><sub>Made with ❤️ for people who hate rebuilding their window layouts every morning.</sub></p>
