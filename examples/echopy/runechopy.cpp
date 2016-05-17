#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/utsname.h>
#include <libgen.h>

int main(int argc, char * const *argv)
{
    const char *exename = "../testecho.py";
    char library_path[4096];
    struct utsname utsname;
    const char *libdir = "./bin";

    fprintf(stderr, "runecho args: ");
    for (int i = 0; i < argc; i++)
      fprintf(stderr, " %s", argv[i]);
    fprintf(stderr, "\n");
    if (argc > 1) {
	exename = argv[1];
	// What? dirname modifies its argument?
	libdir = dirname(strdup(argv[1]));
    }
    uname(&utsname);
    if (strcmp(utsname.machine, "armv7l") == 0) {
	strncpy(library_path, "./bin:../lib:.", sizeof(library_path));
	exename = "../bin/python";
    } else {
	strncpy(library_path, libdir, sizeof(library_path));
    }
    
    if (getenv("LD_LIBRARY_PATH") != 0) {
        strncat(library_path, ":", sizeof(library_path)-strlen(library_path)-1);
        strncat(library_path, getenv("LD_LIBRARY_PATH"), sizeof(library_path)-strlen(library_path)-1);
    }
    fprintf(stderr, "LD_LIBRARY_PATH: %s\n", library_path);
    setenv("LD_LIBRARY_PATH", library_path, 1);
    fprintf(stderr, "%s: execv(%s)\n", argv[0], exename);
    return execv(exename, argv);
}