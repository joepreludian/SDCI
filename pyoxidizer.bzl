def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    manifest = FileManifest()
    manifest.add_python_resource('.', exe)

    log_conf = glob(["log_conf.yaml"])
    manifest.add_manifest(log_conf)
    return manifest

def make_exe():
    dist = default_python_distribution(flavor="standalone_dynamic", python_version="3.10")

    python_config = dist.make_python_interpreter_config()
    python_config.module_search_paths = ["$ORIGIN/lib"]
    #python_config.run_command = "sdci-cli"
    #python_config.run_command = "import sdci"
    #python_config.run_filename = "sdci-server"
    python_config.run_module = "sdci"

    # Policy
    python_policy = dist.make_python_packaging_policy()
    python_policy.resources_location = "in-memory"
    python_policy.resources_location_fallback = "filesystem-relative:lib"
#     python_policy.set_resource_handling_mode("files")
    #python_policy.allow_in_memory_shared_library_loading = True

    executable = dist.to_python_executable(
        "sdci-server",
        config=python_config,
        packaging_policy=python_policy
    )

    executable.add_python_resources(executable.pip_install(["."]))

    return executable

register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)

resolve_targets()