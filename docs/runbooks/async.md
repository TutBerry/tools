# Инструкция по эксплуатации асинхронной части TutBerry

Команды предназначены для оператора развёрнутого окружения, в том числе диагностических заданий GitHub Actions. Не выполнять очистку или повторную доставку в рабочей среде без согласования.

## Состояние очередей

    docker compose exec broker rabbitmqctl list_queues name messages consumers
    docker compose logs --tail=100 worker

Рабочие очереди: booking.notifications и booking.cache. У каждой есть очередь с суффиксом .dlq.

| Признак | Значение |
|---|---|
| messages растёт, consumers = 0 | Worker остановлен |
| messages растёт, consumers > 0 | Обработка не успевает либо повторяется |
| DLQ непуста | Требуется разбор отказов |

## Разбор DLQ

В панели RabbitMQ Management (порт 15672 в учебном окружении) открыть нужную DLQ и Get messages, выбрав режим возврата сообщений в очередь (requeue). Не удалять сообщения при диагностике. Проверить message_id и заголовки x-attempts, x-failure-kind, x-failure-reason, x-failed-at, x-original-routing-key.

| Вид ошибки | Действие |
|---|---|
| PermanentFailure | Исправить данные или причину постоянного отказа |
| TransientFailure | Восстановить зависимость |
| Другие исключения | Проверить журнал, исправить обработчик и выпустить исправление |

Не публиковать содержимое писем и персональные данные в общедоступных логах.

## Возврат сообщений

После устранения причины включить shovel:

    docker compose exec broker rabbitmq-plugins enable rabbitmq_shovel rabbitmq_shovel_management

В Management UI открыть исходную DLQ, выбрать Move messages и указать соответствующую рабочую очередь: booking.notifications либо booking.cache. Если интерфейс не предоставляет Move messages, настроить shovel через Admin с исходной и целевой очередями, подтверждением on-confirm и удалением после опустошения исходной очереди. Не переносить сообщения в общий exchange: это создаст копии у других потребителей.

Сохранять тело, message_id и x-original-routing-key. Заголовок x-attempt удаляется при помещении в DLQ, поэтому попытки начинаются заново. Перенос всей очереди допустим только после проверки всех причин отказов. Проверить журналы и уменьшение длины очереди.

## Кеш и дедупликация

    docker compose exec cache valkey-cli --scan --pattern 'listings:*'
    docker compose exec cache valkey-cli TTL 'listings:<hash>'
    docker compose exec cache valkey-cli DEL 'listings:<hash>'

Заменить <hash> фактическим ключом. Для сброса всех результатов поиска:

    docker compose exec -T cache valkey-cli --scan --pattern 'listings:*' | xargs -r docker compose exec -T cache valkey-cli DEL

Не использовать FLUSHALL или FLUSHDB: они уничтожат отметки дедупликации. PostgreSQL является источником истины для поиска, но processed:* хранится только в Valkey.

    docker compose exec cache valkey-cli GET 'processed:<event_id>'
    docker compose exec cache valkey-cli TTL 'processed:<event_id>'

Заменить <event_id> фактическим идентификатором. Значение done означает завершение (24 часа); случайный токен означает аренду (60 секунд по умолчанию). Не удалять эти ключи вручную.

## Диагностика и восстановление

| Симптом | Проверка |
|---|---|
| Нет письма | Очередь notifications, DLQ, email пользователя, Mailpit (8025), журнал worker |
| Дубли писем | TTL аренды и отметки done, сбой между SMTP и отметкой |
| event_retry_scheduled | Временный отказ или занятая аренда; проверить зависимость |
| Устаревший поиск | Очередь booking.cache, привязки created/cancelled/withdrawn, TTL |
| Медленное бронирование | Журнал API, event_publish_failed, доступность брокера |
| Кеш недоступен | Состояние cache, запросы к PostgreSQL |

    docker compose ps
    docker compose logs --tail=100 api broker cache worker mailpit
    docker compose up -d broker cache mailpit worker

После восстановления проверить доступность API, состояние очередей и отсутствие новых отказов. Потерянные до публикации события автоматически не восстанавливаются: transactional outbox пока отсутствует. Не создавать повторную бронь ради повторного письма.

## Статус проверки

Инструкция соответствует текущим именам очередей и ключей TutBerry. Команды и интерфейс shovel ещё не проверены на развёрнутом окружении; результаты необходимо подтвердить интеграционными проверками.
