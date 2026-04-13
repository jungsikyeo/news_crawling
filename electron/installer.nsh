!macro customInit
  ; 설치 시작 전 실행 중인 NewsDesk 프로세스를 자동 종료
  nsExec::ExecToLog 'taskkill /F /IM "NewsDesk.exe" /T'
  Sleep 1000
!macroend
