# Daily schedule (task 7's cutover target). 21:30 UTC Mon-Fri — after the US close
# (16:00 ET = 20:00 UTC in summer / 21:00 UTC in winter), with margin either way.
resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${var.project}-daily-ingest"
  description         = "Trigger Continuo ingestion after US market close"
  schedule_expression = "cron(30 21 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "daily" {
  rule = aws_cloudwatch_event_rule.daily.name
  arn  = aws_lambda_function.ingest.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}
