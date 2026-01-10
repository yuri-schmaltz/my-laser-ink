# Release e Empacotamento

## Objetivo
Gerar instaladores reproduzíveis e assináveis.

## Targets
- Linux (AppImage/Flatpak/Snap conforme estratégia)
- Windows (MSI/EXE)

## Processo
1. Tag do repositório
2. CI build
3. Rodar testes
4. Gerar artefatos
5. Publicar release notes

## Versão
- Versão do produto deve ser única e semântica
- Compatibilidade de plugins/pacotes deve seguir faixa suportada
