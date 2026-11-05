use std::path::Path;

use serde::Serialize;

use crate::error::CoreResult;
use crate::git;

#[derive(Debug, Clone, Serialize)]
pub struct TrackedSummary {
    pub files: u64,
    pub bytes: u64,
    pub unreadable: u64,
}

/// `git ls-files -v -z`, so non-ASCII paths stay literal (quotePath is a trap).
pub fn tracked_paths(root: &Path) -> CoreResult<Vec<String>> {
    let raw = git::run(root, &["ls-files", "-v", "-z"])?;
    Ok(raw
        .split('\0')
        .filter(|record| record.len() > 3)
        .map(|record| record[2..].replace('\\', "/"))
        .collect())
}

pub fn tracked_summary(root: &Path) -> CoreResult<TrackedSummary> {
    let paths = tracked_paths(root)?;
    let mut bytes = 0_u64;
    let mut unreadable = 0_u64;
    for rel in &paths {
        match root.join(rel).metadata() {
            Ok(meta) => bytes += meta.len(),
            Err(_) => unreadable += 1,
        }
    }
    Ok(TrackedSummary { files: paths.len() as u64, bytes, unreadable })
}
