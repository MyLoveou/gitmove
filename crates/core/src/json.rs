use serde::Serialize;

/// The shared envelope used by CLI `--json`, the daemon and MCP resources.
#[derive(Debug, Serialize)]
pub struct Envelope<T: Serialize> {
    pub schema_version: u32,
    pub tool: String,
    pub ok: bool,
    pub repo: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<T>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<super::error::ErrorPayload>,
}

impl<T: Serialize> Envelope<T> {
    pub fn success(tool: &str, repo: Option<String>, data: T) -> Self {
        Self { schema_version: 1, tool: tool.to_string(), ok: true, repo, data: Some(data), error: None }
    }

    pub fn failure(tool: &str, code: &str, message: &str, steps: Vec<String>) -> Self {
        Self {
            schema_version: 1,
            tool: tool.to_string(),
            ok: false,
            repo: None,
            data: None,
            error: Some(super::error::ErrorPayload {
                code: code.to_string(),
                message: message.to_string(),
                steps,
            }),
        }
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).unwrap_or_else(|_| "{}".to_string())
    }
}
