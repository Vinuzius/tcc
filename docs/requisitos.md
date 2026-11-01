## RF — Requisitos Funcionais

**RF01 – Execução de consultas SQL:** O sistema deverá permitir que usuários realizem consultas ao banco de dados por meio de instruções SQL, especificando as informações que desejam obter.

**RF02 – Identificação do usuário:** O sistema deverá identificar o usuário responsável por cada requisição, permitindo determinar as políticas de privacidade aplicáveis às suas consultas.

**RF03 – Identificação do perfil:** O sistema deverá identificar o perfil de privacidade associado ao usuário responsável pela requisição.

**RF04 – Gerenciamento de perfis:** O sistema deverá permitir que o administrador crie, consulte, atualize e gerencie perfis de privacidade.

**RF05 – Associação de legislações aos perfis:** O sistema deverá permitir que os perfis sejam fundamentados em legislações de proteção de dados, possibilitando a utilização de diretrizes provenientes de uma ou mais legislações.

**RF06 – Gerenciamento de regras de privacidade:** O sistema deverá permitir que o administrador crie, consulte, atualize e gerencie as regras de privacidade associadas aos perfis.

**RF07 – Associação de regras às colunas:** O sistema deverá permitir que as regras de privacidade sejam associadas individualmente a uma coluna ou a um conjunto de colunas das tabelas do banco de dados.

**RF08 – Associação de perfis aos usuários:** O sistema deverá permitir que o administrador atribua perfis de privacidade aos usuários, determinando quais políticas serão aplicadas às suas consultas.

**RF09 – Controle de permissões administrativas:** O sistema deverá restringir as operações de gerenciamento de usuários, perfis e regras de privacidade aos administradores.

**RF10 – Identificação das informações solicitadas:** O sistema deverá analisar as consultas SQL recebidas para identificar as tabelas e colunas envolvidas na solicitação.

**RF11 – Identificação das regras aplicáveis:** O sistema deverá relacionar as informações solicitadas na consulta com as regras de privacidade definidas no perfil associado ao usuário.

**RF12 – Aplicação das regras de privacidade:** O sistema deverá executar as operações de proteção determinadas pelas regras aplicáveis ao perfil do usuário, considerando tanto regras individuais quanto regras associadas a conjuntos de colunas.

**RF13 – Transformação dos dados:** O sistema deverá permitir a aplicação de diferentes operações de proteção aos dados, incluindo mascaramento, generalização, supressão e outras formas de transformação definidas pelas regras de privacidade.

**RF14 – Restrição de acesso às informações:** O sistema deverá impedir que informações não permitidas pelas regras do perfil sejam disponibilizadas ao usuário.

**RF15 – Retorno dos resultados:** O sistema deverá retornar ao usuário os resultados das consultas após a aplicação das regras de privacidade correspondentes ao seu perfil.

## RNF — Requisitos Não Funcionais

**RNF01 – Segurança:** O sistema deverá garantir que os usuários tenham acesso somente às funcionalidades e informações permitidas de acordo com suas atribuições e perfis de privacidade.

**RNF02 – Confidencialidade:** O sistema deverá impedir a exposição de informações protegidas pelas regras de privacidade durante o processamento e a disponibilização dos resultados das consultas.

**RNF03 – Integridade dos dados:** O sistema deverá preservar a integridade dos dados originais armazenados no banco de dados durante o processo de consulta e aplicação das regras de privacidade.

**RNF04 – Consistência dos resultados:** O sistema deverá garantir que os resultados retornados sejam consistentes com a consulta realizada e com as regras de privacidade aplicáveis ao perfil do usuário.

**RNF05 – Conformidade com as políticas de privacidade:** O sistema deverá assegurar que o tratamento e a disponibilização dos dados respeitem as políticas estabelecidas pelos perfis de privacidade.

**RNF06 – Extensibilidade:** O sistema deverá permitir a criação de novos perfis e regras de privacidade sem exigir alterações nas definições dos perfis já existentes.

**RNF07 – Manutenibilidade:** O sistema deverá permitir a manutenção e atualização das regras de privacidade e dos perfis de forma independente, evitando a necessidade de modificar os mecanismos de processamento sempre que uma nova regra for adicionada.

**RNF08 – Modularidade:** O sistema deverá possuir uma organização que permita separar as responsabilidades de gerenciamento de usuários, gerenciamento de perfis, definição de regras e processamento das consultas.