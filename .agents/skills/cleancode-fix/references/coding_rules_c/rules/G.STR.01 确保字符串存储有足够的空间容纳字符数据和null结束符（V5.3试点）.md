# G.STR.01 确保字符串存储有足够的空间容纳字符数据和null结束符（V5.3试点）

- **规则ID**：92f37667-e1e9-4825-9621-67587d28c4d4
- **更新时间**：2025-06-05 04:10:04

---

**【问题级别】**

一般

**【描述】**

// 函数原型

#include <unistd.h>

ssize_t readlink(const char *path, char *buf, size_t bufsiz);



`readlink()`会将参数`path`的符号链接内容存储到参数`buf`所指的内存空间，`buf`不是以`null`结尾的。`readlink()`执行成功则返回字符串的字符数，失败返回-1， 错误代码存于errno。



因此，需要确保返回值不是`-1`（执行不出错）并且小于`buf`所指的内存空间的大小（缓冲区不溢出且有`null`结束符）。

**【正确示例】**

```
场景1：没有检查readlink返回值不是`-1`
- 修复示例：
void ReadlinkGoodCase01()
{
    char filePath[BUF_SIZE];
    ssize_t r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r != -1 && r < sizeof(filePath)) {    
        filePath[r] = '\0';  // 符合: 确认返回值不是-1，并且小于BUF_SIZE
    }
}

场景2：没有检查返回值是否小于字符串`buf`的大小
- 修复示例：
void ReadlinkGoodCase01()
{
    char filePath[BUF_SIZE];
    ssize_t r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r != -1 && r < sizeof(filePath)) {
        filePath[r] = '\0';  // 符合: 确认返回值不是`-1，并且小于BUF_SIZE
    }
}

```
**【错误示例】**

```
场景1：没有检查readlink返回值不是`-1`
- 错误示例：
void ReadlinkBadCase01()
{
    char filePath[BUF_SIZE];
    ssize_t r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r == sizeof(filePath)) {  // 不符合: 没有检查readlink的返回值是否等于-1
        return;
    }

    filePath[r] = '\0'; 
}

场景2：没有检查返回值是否小于字符串`buf`的大小
- 错误示例：
void ReadlinkBadCase02()
{
    char filePath[BUF_SIZE];
    ssize_t r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r == -1) {
        return;
    }
    filePath[r] = '\0';  // 不符合：没有检查readlink的返回值是否小于filePath长度
}

```
**【修复建议】**

正确使用readlink，检查确认返回值不是`-1`并且小于字符串`buf`的大小，确保获取的路径有`null`结束符。
