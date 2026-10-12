# G.STR.02 对字符串进行存储操作，确保字符串有null结束符

- **规则ID**：36a4c0a5-2fd8-4f4a-9f07-84cd132d2cdc
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

1、将数据复制到不足以容纳数据的缓冲区，会导致缓冲区溢出。为了避免这种错误，要确保目的缓冲区大小足以容纳复制数据及null结束符。



2、部分字符串处理函数操作字符串时，将截断超出指定长度的字符串，如strncpy()函数最多复制n个字符到目的缓冲区，如果源字符串长度大于n，则目的缓冲区的内容为n个被复制的字符，null结束符不会被写入到目的缓冲区，因此，对字符串进行存储操作，必须确保字符串有null结束符。

**【正确示例】**

```
##### 场景1：进行数据复制时，未确保目的缓冲区大小足以容纳复制数据及null结束符
- 修复示例1：

```c
#define BUFFSIZE 6
void SecAStringNullCase01Good01()
{
    char dest[BUFFSIZE] = {0};
    char src[] = "12345";
    // Good: dest大小为6，src包含结束符大小为6，dest大小足以容纳结束符。
    memcpy(dest, src, sizeof(src));
    // Good: 使用包含结束符的字符串。
    strchr(dest, '1');
}
```
##### 场景2：对字符串进行存储操作，未确保字符串有null结束符
- 修复示例1：

```c
#define BUFFSIZE 30

void SecAStringNullCase02Good01(int32_t fd)
{
    char name[BUFFSIZE];
    // read函数不会正确给name添加终止符。
    int32_t ret = read(fd, name, BUFFSIZE);
    if (ret == -1) {
        return;
    }
    // 给name正确添加终止符。
    name[BUFFSIZE - 1] = '\0';
    // Good: name正确添加终止符后传递给strcmp。
    strcmp(name, realName);
}
```


```
**【错误示例】**

```
##### 场景1：进行数据复制时，未确保目的缓冲区大小足以容纳复制数据及null结束符
- 错误示例1：

```c
#define BUFFSIZE 5
void SecAStringNullCase01Bad01()
{
    char dest[BUFFSIZE];
    char src[] = "12345";
    // 不符合: dest大小为5，src包含结束符大小为6，dest大小不足以容纳结束符。
    memcpy(dest, src, sizeof(src));
    // 不符合: 使用不包含结束符的字符串。
    strchr(dest, '1');
}
```
##### 场景2：对字符串进行存储操作，未确保字符串有null结束符
- 错误示例1：

```c
#define BUFFSIZE 30

void SecAStringNullCase02Bad01(int32_t fd)
{
    char name[BUFFSIZE];
    // read函数不会正确给name添加终止符。
    int32_t ret = read(fd, name, BUFFSIZE);
    if (ret == -1) {
        return;
    }
    // 不符合: 将未正确添加终止符的name传递给strcmp。
    strcmp(name, realName);
}
```


```
**【修复建议】**

1、进行字符串拷贝时，必须确保目的缓冲区大小足以容纳复制数据及null结束符；

2、进行字符串拷贝时，使用安全函数`strcpy_s`，`strncpy_s`，`wcscpy_s`，`wcsncpy_s`时，如果返回成功，可以确保目的缓冲区以`\0`结尾，无需在拷贝结束后额外添加`\0`结束符。具体请查阅《华为安全函数库说明文档》。
