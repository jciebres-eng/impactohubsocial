# Testes executáveis

Execute na raiz do release:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Os testes cobrem bloqueio determinístico, score explicável, dados ausentes, invariância de plano/voucher e não armazenamento do voucher em texto puro.
