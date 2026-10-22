from __future__ import annotations

import pytest

LANGUAGE_CASES = [
    (
        "ruby",
        "client.rb",
        b'require_relative "service"\nmodule App\n class Client\n # Docs\n def run(value)\n service(value)\n end\n end\nend\n',
        "App.Client.run",
        ["service"],
    ),
    (
        "php",
        "client.php",
        b"<?php\nuse App\\Service;\nclass Client { /** Docs */ public function run($value) { return service($value); } }\n",
        "Client.run",
        ["App\\Service"],
    ),
    (
        "swift",
        "client.swift",
        b"import Foundation\nclass Client {\n /// Docs\n func run(value: Int) -> Int { return service(value) }\n}\n",
        "Client.run",
        ["Foundation"],
    ),
    (
        "kotlin",
        "client.kt",
        b"package app\nimport app.Service\nclass Client {\n /** Docs */\n fun run(value: Int): Int { return service(value) }\n}\n",
        "Client.run",
        ["app.Service"],
    ),
    (
        "scala",
        "client.scala",
        b"import app.Service\nclass Client {\n /** Docs */\n def run(value: Int): Int = { service(value) }\n}\n",
        "Client.run",
        ["app.Service"],
    ),
    (
        "lua",
        "client.lua",
        b'local service = require("service")\n-- Docs\nfunction run(value)\n return service(value)\nend\n',
        "run",
        ["service"],
    ),
    (
        "r",
        "client.R",
        b"library(service)\nrun <- function(value) { service(value) }\n",
        "run",
        ["service"],
    ),
    (
        "bash",
        "client.sh",
        b'# Docs\nrun() {\n service "$1"\n}\nsource ./service.sh\n',
        "run",
        ["./service.sh"],
    ),
    (
        "sql",
        "schema.sql",
        b"CREATE TABLE users (id INT PRIMARY KEY, name TEXT);\nCREATE VIEW names AS SELECT name FROM users;\n",
        "users",
        [],
    ),
    (
        "markdown",
        "README.md",
        b"# Project\n\nDescription text\n\n## Usage\n\nLong example content\n",
        "Usage",
        [],
    ),
    (
        "rst",
        "README.rst",
        b"Project\n=======\n\nDescription\n\nUsage\n-----\n\nExample\n",
        "Usage",
        [],
    ),
    (
        "protobuf",
        "schema.proto",
        b'syntax = "proto3";\nimport "common.proto";\nmessage User { string name = 1; }\nservice Users { rpc Get(User) returns (User); }\n',
        "Users.Get",
        ["common.proto"],
    ),
    (
        "graphql",
        "schema.graphql",
        b"type User { id: ID! name: String }\nquery GetUser { user { id name } }\n",
        "GetUser",
        [],
    ),
    (
        "hcl",
        "main.tf",
        b'resource "aws_instance" "server" {\n ami = "abcdef"\n instance_type = "t2.micro"\n}\n',
        "resource.aws_instance.server",
        [],
    ),
    (
        "dockerfile",
        "Dockerfile",
        b'FROM python:3.12\nWORKDIR /app\nCOPY . .\nRUN pip install .\nCMD ["python", "app.py"]\n',
        "FROM python:3.12",
        [],
    ),
    (
        "make",
        "Makefile",
        b"build: src/main.c\n\tcc -o main src/main.c\n\nclean:\n\trm main\n",
        "build",
        [],
    ),
    (
        "cmake",
        "CMakeLists.txt",
        b'cmake_minimum_required(VERSION 3.20)\nproject(App)\nfunction(build target)\n message(STATUS "Building ${target}")\nendfunction()\n',
        "build",
        [],
    ),
]


@pytest.fixture(params=LANGUAGE_CASES, ids=lambda case: case[0])
def language_case(request: pytest.FixtureRequest) -> tuple[str, str, bytes, str, list[str]]:
    return request.param


@pytest.fixture
def language_files() -> dict[str, tuple[str, bytes]]:
    return {path: (language_id, source) for language_id, path, source, _, _ in LANGUAGE_CASES}


@pytest.fixture
def language_sources() -> dict[str, bytes]:
    return {language_id: source for language_id, _, source, _, _ in LANGUAGE_CASES}
