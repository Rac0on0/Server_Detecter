# Game Server Detector

이 프로그램은 게임 진행 중 내가 연결된 서버의 IP, UDP 포트 및 GeoIP 위치 정보를 화면에 투명 오버레이로 보여주는 도구입니다.  
This is a lightweight, non-intrusive network overlay tool that displays your current game server location (GeoIP) and IP:Port on screen in real-time.

---

사용 예시 ㅣ Use Example

<img width="258" height="265" alt="스크린샷 2026-09-16 001711" src="https://github.com/user-attachments/assets/b3bac081-d6f9-410b-9f2a-0c41179d2325" />

---

## 주요 기능 (Features)

- **백그라운드 패킷 분석 및 CDN 필터링 (Raw Socket & Filtering)**  
  게임 클라이언트 수정이나 메모리 접근 없이 윈도우 네트워크 패킷 헤더만 분석합니다. Cloudflare, Discord, Steam 등 게임 외적 CDN/웹 서비스 패킷을 자동 필터링하여 순수 게임 서버만 추적합니다.  
  **Background Packet Analysis & Filtering**  
  Inspects network packet headers at the OS level without modifying game files or memory. Automatically filters out non-game CDN/web service traffic (Cloudflare, Discord, Steam, etc.).

- **게임 프로세스 모니터링 (Game Process Monitoring)**  
  지정된 게임 프로세스(`prospect-win64-shipping.exe`)의 UDP 연결을 실시간 추적합니다.  
  Tracks active UDP connections of the specified game process (`prospect-win64-shipping.exe`) in real-time.

- **이전 접속 서버 히스토리 (Server History)**  
  최근 접속했던 서버 기록을 최대 5개까지 차례대로 유지합니다. `더보기 ▼ / 접기 ▲` 토글 버튼과 순번별 고유 색상 꼬리표로 시각적 직관성을 제공합니다.  
  Keeps a history of up to 5 recently connected servers. Supports a `More ▼ / Collapse ▲` toggle with color-coded tags for each entry.

- **자동 세션 로깅 (Automatic Session Logging)**  
  새로운 매치 세션에 진입할 때마다 `server_log.txt`에 시간, IP:Port, 서버 위치를 자동 저장합니다.  
  Automatically logs timestamp, IP:Port, and server location to `server_log.txt` upon entering a new match session.

- **트레이 아이콘 및 스마트 위치 저장 (System Tray & Auto Position)**  
  드래그로 오버레이 위치를 이동할 수 있으며, 좌표가 화면 밖으로 잘리지 않도록 자동 보정되어 저장됩니다 (`config.json`). 트레이 아이콘을 통해 안전하게 종료할 수 있습니다.  
  Supports drag-and-drop overlay positioning with auto-clamping to prevent screen boundary cutoff. Saves window coordinates to `config.json` and supports graceful exit via System Tray.

---

## 사용법 및 주의 사항 (Usage & Requirements)

**`Server_Detecter.exe`를 다운받으셔야 합니다.**

1. **관리자 권한 필요 (Admin Privileges Required)**  
   - Raw Socket 패킷 수집 특성상 프로그램 실행 시 **관리자 권한**이 필수입니다.  
   - `Server_Detecter.exe` 우클릭 ➔ **속성** ➔ **호환성** ➔ **[관리자 권한으로 이 프로그램 실행]** 체크 후 실행하는 것을 권장합니다.  
   - Due to Raw Socket packet capturing, **administrator privileges** are required.  
   - Right-click `Server_Detecter.exe` ➔ **Properties** ➔ **Compatibility** ➔ Check **[Run this program as an administrator]**.

2. **프로그램 종료 방법 (How to Exit the Program)**  
   - 작업 표시줄 우측 하단의 **시스템 트레이(▲ 숨겨진 아이콘)** 영역에서 프로그램 아이콘을 마우스 우클릭 후 **`종료`**를 눌러 종료합니다.  
   - Open the **System Tray** (hidden icons area ▲), right-click the program icon, and select **`Quit`** (or **`종료`**).

3. **전용 폴더 생성 권장 (Dedicated Folder Recommended)**  
   - 실행 시 같은 경로에 설정 파일(`config.json`)과 로그 파일(`server_log.txt`)이 자동 생성됩니다. 별도 폴더에서 실행하는 것을 추천합니다.  
   - Configuration (`config.json`) and log files (`server_log.txt`) will be generated in the same directory. Creating a separate folder is recommended.

---

## 백신 오탐 및 차단 해제 방법 (False Positive & Exclusion Guide)

이 프로그램은 PyInstaller 패키징 및 네트워크 패킷 분석(Raw Socket) 특성상 **Windows Defender** 등 일부 백신 프로그램에서 악성코드로 잘못 인식(오탐)하여 실행 파일(`Server_Detecter.exe`)을 차단하거나 삭제할 수 있습니다. 이는 정식 개발자 서명이 없는 자작 프로그램에서 발생하는 일반적인 현상이며, 프로그램은 완전히 안전합니다.

Due to PyInstaller packaging and Raw Socket usage, **Windows Defender** may flag `Server_Detecter.exe` as a False Positive and block or remove it. This is a common occurrence for unsigned custom executables and the program is completely safe to use.

### 차단 해제 방법 (How to Allow the File)

1. **Windows 검색창**에 **`바이러스 및 위험 방지`** 입력 후 실행  
   Search for **`Virus & threat protection`** in the Windows Start menu.
2. **`보호 기록`** 클릭  
   Click on **`Protection history`**.
3. 최근 차단 항목 중 **`Server_Detecter.exe`** 관련 위협 차단 내역 선택  
   Find and click the blocked item related to **`Server_Detecter.exe`**.
4. 우측 하단의 **`작업`** 버튼 클릭 ➔ **`허용`** (또는 **`디바이스에서 허용`**) 선택  
   Click the **`Actions`** button ➔ Select **`Allow`** (or **`Allow on device`**).

---

## 기술적 동작 방식 및 약관 준수 (Technical Notes & Compliance)

- **비인가 변조 없음 (Non-Intrusive)**  
  게임 프로세스나 메모리에 코드를 주입하거나, 변조하거나, 읽지 않습니다.  
  Does **NOT** inject code, read/modify game memory, or alter game files.

- **순수 네트워크 모니터링 (Pure Network Monitoring)**  
  윈도우 Raw Socket(`socket.SOCK_RAW`)을 활용하여 송수신 IP/UDP 헤더 정보만 단순 조회합니다.  
  Operates solely at the OS network level using Windows Raw Sockets (`socket.SOCK_RAW`) to inspect inbound/outbound IP/UDP headers.

- **미인증 및 면책 사항 (Disclaimer & User Responsibility)**  
  본 프로그램은 게임 개발사의 승인을 받지 않은 개인용 유틸리티 툴입니다. 프로그램 사용으로 발생하는 모든 결과 및 책임은 사용자 본인에게 있습니다.  
  This tool is an unofficial, independent utility and is **NOT officially endorsed or approved by the game developers**. Users assume all risks and responsibilities for using this software.

---

## 필요 라이브러리 (Dependencies for Python)

소스 코드를 직접 실행하거나 빌드하는 경우 아래 라이브러리가 필요합니다:  
If running or building the Python source code directly, the following packages are required:

```bash
pip install psutil requests pystray pillow
