!macro customInit
  ; 설치 시작 전 실행 중인 NewsDesk 프로세스를 자동 종료
  nsExec::ExecToLog 'taskkill /F /IM "NewsDesk.exe" /T'
  Sleep 1000
  ; Electron 캐시 삭제 — 이전 버전 UI가 캐시되는 문제 방지
  RMDir /r "$APPDATA\newsdesk\Cache"
  RMDir /r "$APPDATA\newsdesk\Code Cache"
  RMDir /r "$APPDATA\newsdesk\GPUCache"
  RMDir /r "$APPDATA\newsdesk\DawnGraphiteCache"
  RMDir /r "$APPDATA\newsdesk\DawnWebGPUCache"
  RMDir /r "$APPDATA\newsdesk\Network"
  RMDir /r "$APPDATA\newsdesk\blob_storage"
!macroend
