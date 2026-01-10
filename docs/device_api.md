# Device API (Contrato)

## Objetivo
Unificar a interface de comunicação com diferentes controladores (GRBL e outros via serial), reduzindo acoplamento com a UI.

## Interfaces
- DeviceDriver
  - connect/disconnect
  - get_status
  - stream_gcode / send_job
  - pause/resume/abort
  - jog/home/frame

## Capabilities
- protocol (ex.: grbl)
- supports_m4
- max_s_value
- has_homing
- buffer/modelo de streaming (quando necessário)

## Status
- state: disconnected/idle/run/hold/alarm/error
- wpos/mpos
- feed/spindle
- mensagem/alarme

## Erros e Logging
- Exceções devem ser tipadas (DeviceConnectionError, DeviceAlarmError, etc.)
- Todos os jobs devem produzir logs exportáveis (diagnóstico).
