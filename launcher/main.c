#include <errno.h>
#include <dirent.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int parent_directory(char *path) {
    char *separator = strrchr(path, '/');
    if (separator == NULL || separator == path) {
        return -1;
    }
    *separator = '\0';
    return 0;
}

static int set_runtime_variable(
    const char *name,
    const char *contents,
    const char *suffix
) {
    char value[PATH_MAX];
    int length = snprintf(value, sizeof(value), "%s%s", contents, suffix);
    if (length < 0 || (size_t)length >= sizeof(value)) {
        fprintf(stderr, "SakuGIS: path is too long for %s\n", name);
        return -1;
    }
    return setenv(name, value, 1);
}

static int path_exists(const char *path) {
    return access(path, F_OK) == 0;
}

static int find_python_site_packages(
    const char *contents,
    char *result,
    size_t result_size
) {
    char resources[PATH_MAX];
    if (
        snprintf(resources, sizeof(resources), "%s/Resources", contents) >=
        (int)sizeof(resources)
    ) {
        return -1;
    }

    DIR *directory = opendir(resources);
    if (directory == NULL) {
        return -1;
    }

    int found = -1;
    struct dirent *entry;
    while ((entry = readdir(directory)) != NULL) {
        if (strncmp(entry->d_name, "python", 6) != 0) {
            continue;
        }
        int length = snprintf(
            result,
            result_size,
            "%s/%s/site-packages",
            resources,
            entry->d_name
        );
        if (length > 0 && (size_t)length < result_size && path_exists(result)) {
            found = 0;
            break;
        }
    }
    closedir(directory);
    return found;
}

int main(int argc, char **argv) {
    char executable[PATH_MAX];
    uint32_t executable_size = (uint32_t)sizeof(executable);
    if (_NSGetExecutablePath(executable, &executable_size) != 0) {
        fprintf(stderr, "SakuGIS: executable path is too long\n");
        return 70;
    }

    char resolved[PATH_MAX];
    if (realpath(executable, resolved) == NULL) {
        fprintf(stderr, "SakuGIS: cannot resolve executable path: %s\n", strerror(errno));
        return 70;
    }

    if (parent_directory(resolved) != 0 || parent_directory(resolved) != 0) {
        fprintf(stderr, "SakuGIS: invalid application bundle layout\n");
        return 70;
    }
    const char *contents = resolved;

    char modern_resource_root[PATH_MAX];
    snprintf(
        modern_resource_root,
        sizeof(modern_resource_root),
        "%s/Resources/qgis",
        contents
    );
    int modern_layout = path_exists(modern_resource_root);
    const char *resource_suffix = modern_layout ? "/Resources/qgis" : "/Resources";
    const char *prefix_suffix = modern_layout ? "/Resources/qgis" : "/MacOS";
    const char *gdal_suffix = modern_layout
        ? "/Resources/qgis/gdal"
        : "/Resources/gdal";
    const char *proj_suffix = modern_layout
        ? "/Resources/qgis/proj"
        : "/Resources/proj";

    if (
        setenv("SAKUGIS_RUNTIME_CONTENTS", contents, 1) != 0 ||
        setenv("PYTHONDONTWRITEBYTECODE", "1", 1) != 0 ||
        set_runtime_variable("QGIS_PREFIX_PATH", contents, prefix_suffix) != 0 ||
        set_runtime_variable("QGIS_PKG_DATA_PATH", contents, resource_suffix) != 0 ||
        set_runtime_variable("QGIS_PLUGIN_PATH", contents, "/PlugIns/qgis") != 0 ||
        set_runtime_variable("GDAL_DATA", contents, gdal_suffix) != 0 ||
        set_runtime_variable("PROJ_LIB", contents, proj_suffix) != 0 ||
        set_runtime_variable("QT_PLUGIN_PATH", contents, "/PlugIns") != 0 ||
        set_runtime_variable(
            "QT_QPA_PLATFORM_PLUGIN_PATH", contents, "/PlugIns/platforms"
        ) != 0 ||
        set_runtime_variable("QGIS_PLUGINPATH", contents, "/PlugIns/qgis") != 0
    ) {
        fprintf(stderr, "SakuGIS: cannot configure the embedded runtime\n");
        return 70;
    }

    char python_path[PATH_MAX * 4];
    char python_site_packages[PATH_MAX] = "";
    int has_site_packages = (
        find_python_site_packages(
            contents, python_site_packages, sizeof(python_site_packages)
        ) == 0
    );
    int python_path_length;
    if (modern_layout && has_site_packages) {
        python_path_length = snprintf(
            python_path,
            sizeof(python_path),
            "%s/Resources/sakugis:%s:%s/Resources/qgis/python",
            contents,
            python_site_packages,
            contents
        );
    } else {
        python_path_length = snprintf(
            python_path,
            sizeof(python_path),
            "%s/Resources/sakugis:%s/Resources/python",
            contents,
            contents
        );
    }
    if (
        python_path_length < 0 ||
        (size_t)python_path_length >= sizeof(python_path) ||
        setenv("PYTHONPATH", python_path, 1) != 0
    ) {
        fprintf(stderr, "SakuGIS: cannot configure Python path\n");
        return 70;
    }

    const char *home = getenv("HOME");
    if (home != NULL) {
        char config_path[PATH_MAX];
        int length = snprintf(
            config_path,
            sizeof(config_path),
            "%s/Library/Application Support/SakuGIS",
            home
        );
        if (length > 0 && (size_t)length < sizeof(config_path)) {
            setenv("QGIS_CUSTOM_CONFIG_PATH", config_path, 1);
        }
    }

    char python[PATH_MAX] = "";
    if (modern_layout) {
        char macos_directory[PATH_MAX];
        snprintf(
            macos_directory, sizeof(macos_directory), "%s/MacOS", contents
        );
        DIR *directory = opendir(macos_directory);
        if (directory != NULL) {
            struct dirent *entry;
            while ((entry = readdir(directory)) != NULL) {
                if (strncmp(entry->d_name, "python3.", 8) != 0) {
                    continue;
                }
                snprintf(
                    python,
                    sizeof(python),
                    "%s/%s",
                    macos_directory,
                    entry->d_name
                );
                if (access(python, X_OK) == 0) {
                    break;
                }
                python[0] = '\0';
            }
            closedir(directory);
        }
        if (python[0] != '\0') {
            set_runtime_variable("PYTHONHOME", contents, "/Frameworks");
        }
    } else {
        snprintf(python, sizeof(python), "%s/MacOS/bin/python3", contents);
    }
    if (python[0] == '\0' || access(python, X_OK) != 0) {
        fprintf(stderr, "SakuGIS: embedded Python was not found\n");
        return 70;
    }

    char **python_argv = calloc((size_t)argc + 3, sizeof(char *));
    if (python_argv == NULL) {
        fprintf(stderr, "SakuGIS: cannot allocate launcher arguments\n");
        return 71;
    }

    python_argv[0] = python;
    python_argv[1] = "-m";
    python_argv[2] = "sakugis";
    for (int index = 1; index < argc; ++index) {
        python_argv[index + 2] = argv[index];
    }
    python_argv[argc + 2] = NULL;

    execv(python, python_argv);
    fprintf(stderr, "SakuGIS: cannot launch embedded Python: %s\n", strerror(errno));
    free(python_argv);
    return 70;
}
