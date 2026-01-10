# Driver GRBL 1.1 (Serial)

## Objetivo
Suportar GRBL 1.1 de forma robusta e previsível.

## Handshake
- Abrir serial
- Ler banner (Grbl 1.1x)
- Consultar $$ (capturar $30 e $32)
- Configurar modos padrão: G21/G90/G17/G94

## Status
- Poll com '?'
- Parse de <State|MPos/WPos|FS:...>
- Mapear estados para DeviceStatus

## Controle
- pause: '!'
- resume: '~'
- abort: soft-reset + dreno + estado seguro (política definida)

## Laser (G-code)
- M4 preferido para gravação (dinâmico), M3 para corte quando necessário
- S escalado para 0..$30
- Laser OFF em travel (M5 e/ou S0)

## Frame
- BBox do job (considerando overscan/kerf)
- Movimento com laser OFF

## Testes
- Simulador serial (ok/error, delays)
- Casos: long job, pause/resume, alarm, reconexão
