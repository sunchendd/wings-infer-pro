# G.STD.15-CPP 禁止外部可控数据作为进程启动函数的参数或者作为dlopen/LoadLibrary等模块加载函数的参数

- **规则ID**：b39598f8-3910-4691-8643-c750441babc9
- **更新时间**：2025-03-25 19:23:32

---

**【问题级别】**

一般

**【描述】**

本条款中进程启动函数包括system、popen、execl、execlp、execle、execv、execvp等。



system()、popen()等函数会创建一个新的进程，如果外部可控数据作为这些函数的参数，会导致注入漏洞。



使用execl()等函数执行新进程时，如果使用shell启动新进程，则同样存在命令注入风险。



使用execlp()、execvp()、execvpe()函数依赖于系统的环境变量PATH来搜索程序路径，使用它们时应充分考虑外部环境变量的风险，或避免使用这些函数。



因此，总是优先考虑使用C标准函数实现需要的功能。如果确实需要使用这些函数，应使用白名单机制确保这些函数的参数不受任何外来数据的影响。



使用dlopen、LoadLibrary函数会加载外部模块，如果外部可控数据作为这些函数的参数，有可能会加载攻击者事先预制的模块。如果要使用这些函数，可以采用如下措施之一：



使用白名单机制，确保这些函数的参数不受任何外来数据的影响

使用数字签名机制保护要加载的模块，充分保证其完整性

在设备本地加载的动态库通过权限与访问控制措施保证了本身安全性后，通过特定目录自动被程序加载

在设备本地的配置文件通过权限与访问控制措施保证了本身安全性后，自动加载配置文件中指定的动态库

**【正确示例】**

```
如下代码中，使用C++17提供的文件复制函数实现了文件复制的功能，避免了对cp或cat命令的调用。需要注意的是，为简化描述，下面代码仅供参考。

bool WriteDataToFile(const std::string& dstFilePath, const std::string& srcFilePath)
{
    std::error_code errorCode;
    bool success = std::filesystem::copy_file(srcFilePath, dstFilePath, errorCode);
    if (!success) {
        ... // 错误处理
    }
    return success;
}
如果确实需要调用单个命令，应使用exec*函数来实现参数化调用，并对调用的命令实施白名单管理。同时应避免使用execlp、execvp、execvpe函数，因为这几个函数依赖外部的PATH环境变量。
此时，外部输入的fileName仅作为some_tool命令的参数，没有命令注入的风险。

pid_t pid;
char* const envp[] = {nullptr};
...
std::string fileName = GetDirNameFromRemote();
...
pid = fork();
if (pid < 0) {
    ... // 错误处理
} else if (pid == 0) {
    // 使用some_tool对指定文件进行加工
    execle("/bin/some_tool", "some_tool", fileName.c_str(), nullptr, envp);
    _Exit(-1);
}
...
在必须使用system等命令解析器执行命令时，应对输入的命令字符串基于合理的白名单检查，避免命令注入。

std::string cmd = GetCmdFromRemote();

// 使用白名单检查命令是否合法，仅允许"some_tool_a", "some_tool_b"命令，外部无法随意控制
if (!IsValidCmd(cmd.c_str())) {
    ... // 错误处理
}
system(cmd.c_str());
...

```
**【错误示例】**

```
如下代码中，从外部获取数据后直接作为LoadLibrary函数的参数，有可能导致程序被植入木马。

char* msg = GetMsgFromRemote();
LoadLibrary(msg);
如下代码中，使用 system() 函数执行 cmd 命令串来自外部，攻击者可以执行任意命令：

std::string cmd = GetCmdFromRemote();
system(cmd.c_str());
如下代码中，使用 system() 函数执行 cmd 命令串的一部分来自外部，攻击者可能输入 some dir;reboot字符串，创造成系统重启：

std::string name = GetDirNameFromRemote();
std::string cmd{"ls " + name};
system(cmd.c_str());
使用exec系列函数来避免命令注入时，注意exec系列函数中的path、file参数禁止使用命令解析器(如/bin/sh)。

int execl(const char* path, const char* arg, ...);
int execlp(const char* file, const char* arg, ...);
int execle(const char* path, const char* arg, ...);
int execv(const char* path, char* const argv[]);
int execvp(const char* file, char* const argv[]);
int execvpe(const char* file, char* const argv[], char* const envp[]);
例如，禁止如下使用方式：

std::string cmd = GetDirNameFromRemote();
execl("/bin/sh", "sh", "-c", cmd.c_str(), nullptr);
在Linux下可以使用库函数，或者可以通过编写少量的代码来避免使用system函数调用命令，如mkdir()函数可以实现mkdir命令的功能。
如下代码中，应该避免使用cp命令实现文件内容复制的功能。

int WriteDataToFile(const char* dstFile, const char* srcFile)
{
    ...  // 入参的合法性校验
    std::ostringstream oss;
    oss << "cp " << srcFile << "  " << dstFile;

    std::string cmd{oss.str()};
    system(cmd.c_str());
    ...
}

```
**【修复建议】**

输入校验包括但不局限于： 校验数据长度校验数据范围校验数据类型和格式校验输入只包含可接受的字符（“白名单”形式），尤其需要注意一些特殊情况下的特殊字符。
