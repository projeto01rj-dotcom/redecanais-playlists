# RedeCanaisTV Playlists

Este repositório coleta diariamente o catálogo público de `redecanaistv.app` e publica playlists organizadas por categoria.

## Playlists publicadas

Os arquivos públicos ficam disponíveis diretamente no branch `main` em:

- `https://raw.githubusercontent.com/projeto01rj-dotcom/redecanais-playlists/main/public/canais-tv.m3u8`
- `https://raw.githubusercontent.com/projeto01rj-dotcom/redecanais-playlists/main/public/desenhos.m3u8`
- `https://raw.githubusercontent.com/projeto01rj-dotcom/redecanais-playlists/main/public/filmes.m3u8`
- `https://raw.githubusercontent.com/projeto01rj-dotcom/redecanais-playlists/main/public/series.m3u8`
- `https://raw.githubusercontent.com/projeto01rj-dotcom/redecanais-playlists/main/public/players-fallback.m3u8`
- `https://raw.githubusercontent.com/projeto01rj-dotcom/redecanais-playlists/main/public/status.json`

O GitHub Pages não foi ativado automaticamente porque a integração autenticada não possui a permissão administrativa necessária. As URLs `raw.githubusercontent.com` já são públicas e podem ser incluídas diretamente em players M3U. Se quiser o domínio Pages no futuro, ative **Settings > Pages > Source: GitHub Actions** no repositório.

A lista `players-fallback.m3u8` contém páginas de player quando não foi encontrado um manifesto `.m3u8` direto. As listas de categoria também mantêm esses canais, usando o player como fallback para não deixar filmes ou séries fora do catálogo. Aplicativos IPTV que aceitam somente HLS podem não reproduzir essas entradas.

## Alterar o horário

Edite `.github/workflows/sync.yml` e procure o comentário `COLETA DIÁRIA`. O horário está nesta linha:

```yaml
- cron: "17 3 * * *"
```

O formato é `minuto hora dia-do-mês mês dia-da-semana`, em UTC. Exemplos já estão comentados no arquivo. O workflow atual executa uma vez por dia, às 03:17 UTC, que corresponde a 00:17 no horário de Brasília quando não há mudança de horário local.

Após editar, faça commit e push. Também é possível iniciar imediatamente em **Actions > Sincronizar playlists > Run workflow**.

## Funcionamento

O script `sync.py` coleta as páginas de canais, identifica players e tenta localizar manifestos HLS `.m3u8` no HTML da página e do iframe. As fontes diretas entram na lista da categoria. Quando somente um iframe é encontrado, ele é enviado para a lista de fallback.

O workflow valida os arquivos e salva alterações na pasta `public` do repositório. O arquivo `status.json` registra a última execução e a quantidade de entradas geradas.

A automação deve ser usada somente com fontes que o administrador do site esteja autorizado a redistribuir. O coletor não contorna DRM, login, bloqueios ou controles de acesso.
