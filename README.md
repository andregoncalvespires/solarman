# Solarman (Deye) para Home Assistant

Fork mantido da integração [StephanJoubert/home_assistant_solarman](https://github.com/StephanJoubert/home_assistant_solarman),
que foi arquivada. Comunicação local (porta 8899) com data loggers Solarman V5 e inversores Deye e outros.

Este fork acrescenta:

- Consultas **cientes do sol**: não tenta conectar após o pôr do sol (menos logs de aviso).
- Correções de *blocking call* e de recarga da integração.

> Instalação: HACS → Repositórios personalizados → `andregoncalvespires/solarman` (categoria *Integração*).

## Licença e atribuição

O código-base é do projeto upstream acima; a licença original deve ser mantida
(pendência: copiar o arquivo `LICENSE` do upstream para este repositório).
