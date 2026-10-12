# G.FUU.17 禁止外部可控数据作为dlopen/LoadLibrary等模块加载函数的参数

- **规则ID**：3d9cdf6e-04c0-4807-bf08-b04111e0d356
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

来自程序外部的数据通常被认为是不可信的，在使用这些数据之前，需要进行合理的校验，否则将可能导致不可预期的安全风险。



输入校验包括但不局限于：



1. 校验数据长度

2. 校验数据范围

3. 校验数据类型和格式

4. 校验输入只包含可接受的字符（“白名单”形式），尤其需要注意一些特殊情况下的特殊字符

**【正确示例】**

```
##### 场景1：外部数据未经校验作为数组下标

- 修复示例：外部数据作为数组索引时，必须进行校验，确保不超过数组上下边界。

```c
void TestGood01()
{
    int data[DATA_LEN] = {0};
    int a = getchar();              // getchar获取外部数据
    if (a >= 0 && a < DATA_LEN) {
        data[a] = GetData();        // 符合：数组下标已进行合理的校验
    }
}
```

##### 场景2：外部数据未经校验作为循环上限

- 修复示例：外部数据中的整数值，在作为循环上限前必须进行合理的校验。

```c
#define ARR_SIZE 64
char *g_keyobject[ARR_SIZE];

void ParseKeyGood01(char *bufferTotal, int numKeys)
{
    // 充分校验外部数据
    if (numKeys <= 0 || numKeys > ARR_SIZE) {
        return;
    }

    // 符合：循环上限已进行合理的校验
    for (int i = 0; i < numKeys; i++) {
        g_keyobject[i] = bufferTotal + (1 + 3 * i);
    }
}

int main(int argc, char **argv)
{
    // 从命令行获取的不可信的数据作为参数
    ParseKeyGood01(argv[0], *argv[1]);
    return 0;
}
```

##### 场景3：申请内存的大小来自外部数据时，未进行合法性校验

- 修复示例：申请内存的大小来自外部数据时，必须进行合法性校验。

```c
void UseNumber(int size)
{
    // 本函数内，对size做合法性校验，MAX_LEN被定义为符合程序设计预期的最大内存空间
    if (size <= 0 || size > MAX_LEN) {
        ... // 错误处理
    }
    // 符合：外部数据作为内存申请大小之前，已进行了符合程序需要的合法性校验
    char *buffer = (char *)malloc(size);
    ...
    free(buffer);
    ...
}

int main(int argc, char *argv[])
{
    FILE *fp = fopen("file.txt", "r");;
    if (fp == NULL) {
        return 0;
    }
    int num;
    fscanf(fp, "%d", &num);
    UseNumber(num); // 从文件获取的不可信的数据作为参数
    fclose(fp);
    return 0;
}
```

##### 场景4：外部输入作为内存操作相关函数的复制长度时，未进行合法性校验

- 修复示例：外部输入作为内存操作相关函数的复制长度时，需要检验其合法性。

```c
typedef struct {
    size_t count;
    int val[MAX_NUMBERS];
} ValueTable;

ValueTable *ValueTableDup(const ValueTable *inputTable)
{
    ValueTable *OutputTable = ... // 分配内存
    ...
    // 对inputTable->count做合法性校验
    if (inputTable->count >
        sizeof(OutputTable->val) / sizeof(OutputTable->val[0]) {
        return nullptr;
    }
    errno_t ret = memcpy_s(OutputTable->val, MAX_NUMBERS, inputTable->val, inputTable->count); // 符合
    ...
}
```

##### 场景5：外部可控数据直接作为进程启动函数的参数

模型配置： 配置 AllowedWhiteWord 为清污函数

- 修复示例：外部数据作为进程启动函数参数时，需要进行白名单校验。

```c
void MySystem(const char *userinput)
{
    // 检查是否包含常见命令注入字符：'|',';','>','
'等
    if (!AllowedWhiteWord(userinput)) {
        return;
    }

    char cmd[CMD_MAX] = "/usr/bin/cat ";
    errno_t rc = strcat_s(cmd, CMD_MAX, userinput); // 拼接已检验过的外部输入命令
    if (rc != EOK) {
        ... // 错误处理
    }
    system(cmd); // 符合
}

int main(int argc, char *argv[])
{
    if (argc > 1) {
        char *userinput = argv[1];
        MySystem(userinput); // 从命令行获取的不可信的数据作为参数
    }
    return 0;
}
```
##### 场景6：外部可控数据直接作为dlopen/LoadLibrary等模块加载函数的参数

模型配置： 配置 AllowedWhiteWord 为清污函数

- 修复示例：外部数据作为dlopen/LoadLibrary等模块加载函数的参数时，需要进行白名单校验。

```c
void TestGood01(char *path)
{
    if (AllowedWhiteWord(path)) {               // 外部数据，进行白名单校验
        void *handle = dlopen(path, RTLD_NOW);  // 符合：外部数据已校验
        if (handle == nullptr) {
            return;
        }
        ...
        dlclose(handle);
    }
}

int main(int argc, char *argv[])
{
    TestGood01(argv[1]); // 从命令行获取的不可信的数据作为参数
    return 0;
}
```

##### 场景7：直接使用外部数据拼接SQL命令

模型配置： 配置 GetUserInput 返回值为污染源，mysql_query 第二个参数为污染点，AllowedWhiteWord 为污染清理函数

- 修复示例：使用外部数据拼接SQL命令时，必须进行白名单校验。

```c
void TestGood01()
{
    char name[NAME_MAX];
    char sqlStatements[SQL_CMD_MAX];
    GetUserInput(name, NAME_MAX); // 获取外部数据
    // 外部数据校验是否包含常见的sql注入字符
    if (!AllowedWhiteWord(name)) {
        return;
    }

    // 拼接已校验过的外部数据
    int ret = sprintf_s(sqlStatements, SQL_CMD_MAX, "SELECT childinfo FROM children WHERE name= ‘%s’", name);
    ...
    if (mysql_query(&myConnection, sqlStatements)) { // 符合
        ...
    }
}
```

```
**【错误示例】**

```
##### 场景1：外部数据未经校验作为数组下标

- 错误示例：

```c
void TestBad01()
{
    int data[DATA_LEN] = {0};
    int a = getchar();  // getchar获取外部数据
    data[a] = 1;        // 不符合：外部数据未经校验作为数组下标，可能导致缓冲区溢出
}
```

##### 场景2：外部数据未经校验作为循环上限

- 错误示例：

```c
#define ARR_SIZE 64
char *g_keyobject[ARR_SIZE];

void ParseKeyBad01(char *bufferTotal, int numKeys)
{
    // 不符合：外部数据未经校验作为循环上限，可能导致数组越界
    for (int i = 0; i < numKeys; i++) {
        // g_keyobject 数组的索引受 numKeys 限制，而 numKeys 为外部输入,可使数组索引越界
        g_keyobject[i] = bufferTotal + (1 + 3 * i);
    }
}

int main(int argc, char **argv)
{
    // 从命令行获取的不可信的数据作为参数
    ParseKeyBad01(argv[0], *argv[1]);
    return 0;
}
```

##### 场景3：申请内存的大小来自外部数据时，未进行合法性校验

- 错误示例：

```c
void UseNumber(int size)
{
    // 不符合：外部数据作为内存申请大小之前未校验，可能导致申请内存过大或过小
    char *buffer = (char *)malloc(size);
    ...
    free(buffer);
    ...
}

int main(int argc, char *argv[])
{
    FILE *fp = fopen("file.txt", "r");;
    if (fp == NULL) {
        return 0;
    }
    int num;
    fscanf(fp, "%d", &num);
    UseNumber(num); // 从文件获取的不可信的数据作为参数
    fclose(fp);
    return 0;
}
```

##### 场景4：外部输入作为内存操作相关函数的复制长度时，未进行合法性校验

模型配置：配置 ValueTableDup 第一个参数为污染源

- 错误示例：

```c
typedef struct {
    size_t count;
    int val[MAX_NUMBERS];
} ValueTable;

ValueTable *ValueTableDup(const ValueTable *inputTable)
{
    ValueTable *OutputTable = ... // 分配内存
    ...
    errno_t r = memcpy_s(OutputTable->val, MAX_NUMBERS, inputTable->val, inputTable->count); // 不符合：inputTable->count来自外部数据，使用前未进行合法性校验
    ...
}
```

##### 场景5：外部可控数据直接作为进程启动函数的参数

- 错误示例：

```c
void MySystem(const char *userinput)
{
    char cmd[CMD_MAX] = "/usr/bin/cat ";
    errno_t rc = strcat_s(cmd, CMD_MAX, userinput); // 拼接外部输入命令
    if (rc != EOK) {
        ... // 错误处理
    }
    system(cmd); // 不符合：外部数据经拼接后，未经校验作为system函数的参数，导致命令注入
}

int main(int argc, char *argv[])
{
    if (argc > 1) {
        char *userinput = argv[1];
        MySystem(userinput); // 从命令行获取的不可信的数据作为参数
    }
    return 0;
}
```

##### 场景6：外部可控数据直接作为dlopen/LoadLibrary等模块加载函数的参数

- 错误示例：

```c
void TestBad01(char *path)
{
    void *handle = dlopen(path, RTLD_NOW); // 不符合：外部可控数据作为dlopen等模块加载函数的参数
    if (handle == nullptr) {
        return;
    }
    ...
    dlclose(handle);
}

int main(int argc, char *argv[])
{
    TestBad01(argv[1]); // 从命令行获取的不可信的数据作为参数
    return 0;
}
```

##### 场景7：直接使用外部数据拼接SQL命令

模型配置： 配置 GetUserInput 返回值为污染源，mysql_query 第二个参数为污染点，AllowedWhiteWord 为污染清理函数

- 错误示例：

```c
void TestBad01()
{
    char name[NAME_MAX];
    char sqlStatements[SQL_CMD_MAX];
    GetUserInput(name, NAME_MAX); // 获取外部数据

    // 拼接外部数据
    int ret = sprintf_s(sqlStatements, SQL_CMD_MAX, "SELECT childinfo FROM children WHERE name= ‘%s’", name);
    ...
    if (mysql_query(&myConnection, sqlStatements)) { // 不符合：执行直接拼接外部数据的SQL命令
        ...
    }
}
```

```
**【修复建议】**

1. 外部数据中的整数值，在使用前必须进行合理的校验；

2. 外部数据作为数组索引时，必须进行校验，确保不超过数组上下边界；

3. 申请内存的大小来自外部数据时，必须进行合法性校验；

4. 外部输入作为内存操作相关函数的复制长度时，需要检验其合法性；

5. 外部数据作为进程启动函数参数、或dlopen/LoadLibrary等模块加载函数的参数时，需要进行白名单校验；

6. 使用外部数据拼接SQL命令时，必须进行白名单校验。
