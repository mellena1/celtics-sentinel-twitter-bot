terraform {
  backend "s3" {
    bucket = "celtics-sentinel-twitter-bot"
    key    = "terraform-state.json"
    region = "us-east-1"
  }
}

resource "aws_iam_role" "celtics_sentinel_twitter_bot_role" {
  name = "celtics_sentinel_twitter_bot_role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_iam_policy" "celtics_sentinel_twitter_bot_policy" {
  name        = "celtics_sentinel_twitter_bot_policy"
  path        = "/"
  description = "IAM policy for celtics sentiel twitter bot"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:527169047602:/aws/lambda/celtics_sentinel_twitter_bot",
      "Effect": "Allow"
    },
    {
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:527169047602:/aws/lambda/celtics_sentinel_twitter_bot:*",
      "Effect": "Allow"
    },
    {
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::celtics-sentinel-twitter-bot/credentials.json",
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "celtics_sentinel_twitter_bot_policy_attach" {
  role       = aws_iam_role.celtics_sentinel_twitter_bot_role.name
  policy_arn = aws_iam_policy.celtics_sentinel_twitter_bot_policy.arn
}

resource "aws_lambda_function" "celtics_sentinel_twitter_bot_lambda" {
  filename      = "../lambda.zip"
  function_name = "celtics_sentinel_twitter_bot"
  role          = aws_iam_role.celtics_sentinel_twitter_bot_role.arn
  handler       = "bot.handler"

  source_code_hash = filebase64sha256("../lambda.zip")

  runtime = "python3.8"

  environment {
    variables = {
      ENVIRONMENT = "lambda"
    }
  }
}

resource "aws_cloudwatch_event_rule" "every_fifteen_minutes" {
    name = "every-fifteen-minutes"
    description = "Fires every fifteen minutes"
    schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "run_lambda_every_fifteen_minutes" {
    rule = aws_cloudwatch_event_rule.every_fifteen_minutes.name
    target_id = "run_celtics_sentinel_bot"
    arn = aws_lambda_function.celtics_sentinel_twitter_bot_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_check_foo" {
    statement_id = "AllowExecutionFromCloudWatch"
    action = "lambda:InvokeFunction"
    function_name = aws_lambda_function.celtics_sentinel_twitter_bot_lambda.function_name
    principal = "events.amazonaws.com"
    source_arn = aws_cloudwatch_event_rule.every_fifteen_minutes.arn
}
