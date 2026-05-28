// Test file: Intentional bugs for GuardianAI verification
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

// Bug 1: RESOURCE_LEAK - file handle never closed
int read_config(const char* path) {
    FILE* fp = fopen(path, "r");
    if (!fp) return -1;
    
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), fp)) {
        if (strstr(buffer, "error")) {
            return -2;  // LEAK: fp not closed on early return
        }
    }
    fclose(fp);
    return 0;
}

// Bug 2: NULL_RETURNS - unchecked malloc
char* duplicate_string(const char* src) {
    size_t len = strlen(src);
    char* dst = (char*)malloc(len + 1);
    // BUG: No null check on malloc return
    strcpy(dst, src);
    return dst;
}

// Bug 3: BUFFER_OVERRUN
void process_name(const char* input) {
    char name[32];
    strcpy(name, input);  // BUG: No bounds checking, potential overflow
    printf("Name: %s\n", name);
}

// Bug 4: USE_AFTER_FREE
void process_data() {
    int* data = (int*)malloc(100 * sizeof(int));
    if (!data) return;
    
    for (int i = 0; i < 100; i++) data[i] = i;
    free(data);
    
    // BUG: accessing freed memory
    printf("First element: %d\n", data[0]);
}

// Bug 5: UNINIT - uninitialized variable used
int compute_result(int mode) {
    int result;
    if (mode == 1) {
        result = 42;
    }
    // BUG: result may be uninitialized if mode != 1
    return result;
}

// Bug 6: HARDCODED_CREDENTIALS
void connect_to_db() {
    const char* password = "admin123!secret";
    const char* api_key = "sk-proj-abcdef123456789";
    printf("Connecting with key: %s\n", api_key);
}

// Bug 7: TAINTED_STRING - command injection
void run_command(const char* user_input) {
    char cmd[512];
    sprintf(cmd, "ls %s", user_input);  // BUG: unsanitized input in system command
    system(cmd);
}

// Bug 8: INTEGER_OVERFLOW
int multiply_values(int a, int b) {
    return a * b;  // BUG: no overflow check
}

// Bug 9: DOUBLE_FREE
void cleanup(char* ptr) {
    if (ptr) {
        free(ptr);
    }
    // ... some other logic ...
    free(ptr);  // BUG: freeing already freed pointer
}

// Bug 10: DEADCODE
int validate_input(int x) {
    if (x > 0) {
        return 1;
    } else if (x <= 0) {
        return 0;
    }
    return -1;  // BUG: dead code, can never reach here
}
