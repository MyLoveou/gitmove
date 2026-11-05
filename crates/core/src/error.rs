use std::fmt;

use serde::Serialize;

/// Errors carry a stable code so the UI/MCP can show remediation (1.x F13 style).
#[derive(Debug)]
pub struct CoreError {
    pub code: &'static str,
    pub message: String,
    pub steps: Vec<String>,
}

impl CoreError {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self { code, message: message.into(), steps: Vec::new() }
    }

    pub fn with_steps(mut self, steps: Vec<String>) -> Self {
        self.steps = steps;
        self
    }
}

impl fmt::Display for CoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for CoreError {}

impl From<std::io::Error> for CoreError {
    fn from(value: std::io::Error) -> Self {
        CoreError::new("IO_ERROR", value.to_string())
    }
}

impl From<rusqlite::Error> for CoreError {
    fn from(value: rusqlite::Error) -> Self {
        CoreError::new("INDEX_ERROR", value.to_string())
    }
}

impl From<toml::de::Error> for CoreError {
    fn from(value: toml::de::Error) -> Self {
        CoreError::new("TOML_ERROR", value.to_string())
    }
}

pub type CoreResult<T> = Result<T, CoreError>;

#[derive(Debug, Serialize)]
pub struct ErrorPayload {
    pub code: String,
    pub message: String,
    pub steps: Vec<String>,
}
