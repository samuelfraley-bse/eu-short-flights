# paths.R — Shared path configuration for the short-flights project.
#
# Source this from any script in scripts/ like so:
#
#   source(file.path(
#     if (length(.arg <- grep("^--file=", commandArgs(), value = TRUE)))
#       dirname(normalizePath(sub("^--file=", "", .arg[1]), mustWork = FALSE))
#     else "scripts",
#     "paths.R"
#   ))
#   rm(.arg)
#
# In R Markdown files, source via here instead (WD = Rmd folder, not project root):
#
#   source(here::here("scripts", "paths.R"))
#
# Works whether the script is run via:
#   - Rscript scripts/foo.R               (command line, --file= arg)
#   - Source button / interactive RStudio  (here finds .Rproj root)
#   - knitr / Rmd chunks                  (here finds .Rproj root)

root_dir <- local({
  # Priority 1: here package — reliable in RStudio and knitr regardless of WD
  if (requireNamespace("here", quietly = TRUE))
    return(here::here())

  # Priority 2: --file= argument — reliable when run via Rscript
  arg <- grep("^--file=", commandArgs(), value = TRUE)
  if (length(arg))
    return(normalizePath(file.path(dirname(sub("^--file=", "", arg[1])), ".."),
                         mustWork = TRUE))

  # Fallback: working directory (works if WD happens to be project root)
  normalizePath(getwd(), mustWork = TRUE)
})

data_raw   <- file.path(root_dir, "data", "raw")
data_clean <- file.path(root_dir, "data", "clean")
outputs    <- file.path(root_dir, "data", "clean", "outputs")

dir.create(outputs, recursive = TRUE, showWarnings = FALSE)
