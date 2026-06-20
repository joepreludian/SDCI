# Version

Both SDCI binaries expose a `--version` flag that prints the installed package
version and exits immediately, without running any command.

```bash
$ sdci-server --version
sdci-server, version 1.2.0

$ sdci-cli --version
sdci-cli, version 1.2.0
```

The version is read at runtime from the installed package metadata
(`importlib.metadata.version("sdci")`), so it always reflects the version that is
actually installed in the active environment.

On `sdci-cli`, `--version` is *eager*: it is handled before the usual
`[ SDCI-CLI v… ]` banner, so the only output is the version line.
