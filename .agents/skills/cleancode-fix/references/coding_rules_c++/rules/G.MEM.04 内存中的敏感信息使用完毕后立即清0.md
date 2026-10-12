# G.MEM.04 内存中的敏感信息使用完毕后立即清0

- **规则ID**：fd99ab6a-12ae-4dac-a276-5e80bac66f65
- **更新时间**：2025-03-25 19:24:15

---

**【问题级别】**

严重

**【描述】**

内存中的口令、密钥等敏感信息使用完毕后立即清0，避免被攻击者获取或者无意间泄露给低权限用户。这里所说的内存包括但不限于：



动态分配的内存

静态分配的内存

自动分配（堆栈）内存

内存缓存

磁盘缓存

**【正确示例】**

```
【正例】
下面是另外一个涉及敏感信息清理的场景，在代码获取到密码后，将密码保存到password中，进行密码验证，使用完毕后，通过memset_s()函数对password清0。

int Foo(void)
{
    char password[MAX_PWD_LEN];
    if (!GetPassword(password, sizeof(password))) {
        ...
    }
    if (!VerifyPassword(password)) {
        ...
    }
    ...
    (void)memset_s(password, sizeof(password), 0, sizeof(password));
    ...
}
要特别注意：对敏感信息清理的时候要同时防止因编译器优化而使清理代码无效。

例如，下列代码使用了可能被编译器优化掉的语句。

int SecureLogin(void)
{
    char pwd[PWD_SIZE];
    if (RetrievePassword(pwd, sizeof(pwd))) {
        ... // 口令检查及其他处理
    }
    memset(pwd, 0, sizeof(pwd)); // 编译器优化有可能会使该语句失效
    ...
}
某些编译器在优化时候不会执行它认为不会改变程序执行结果的代码，因此memset()操作会被优化掉。

以下列出了几种可能的解决方法，其中的某些方法不具有普适性，因此需要结合实际选择相应的方法。

可以使用华为安全函数库中的memset_s()函数来避免因编译器优化导致敏感信息清理失败。

int SecureLogin(void)
{
    char pwd[PWD_SIZE];
    if (RetrievePassword(pwd, sizeof(pwd))) {
        ... // 口令检查及其他处理
    }
    (void)memset_s(pwd, sizeof(pwd), 0, sizeof(pwd));
    ...
}
如果编译器支持#pragma指令，那么可以使用该指令指示编译器不作优化。

void SecureLogin(void)
{
    char pwd[PWD_SIZE];
    if (RetrievePassword(pwd, sizeof(pwd))) {
        ... // 口令检查及其他处理
    }
    #pragma optimize("", off)
    // 清除内存
    ...
    #pragma optimize("", on)
    ...
}

```
**【错误示例】**

```
通常内存在释放前不需要清除内存数据，因为这样在运行时会增加额外开销，所以在这段内存被释放之后，之前的数据还是会保留在其中。如果这段内存中的数据包含敏感信息，则可能会意外泄露敏感信息。为了防止敏感信息泄露，必须先清除内存中的敏感信息，然后再释放。
在如下代码示例中，存储在所引用的动态内存中的敏感信息secret被复制到新动态分配的缓冲区newSecret，最终通过free()释放。因为释放前未清除这块内存数据，这块内存可能被重新分配到程序的另一部分，之前存储在newSecret中的敏感信息可能会无意中被泄露。

char *secret = NULL;
/*
 * 假设 secret 指向敏感信息，敏感信息的内容是长度小于SIZE_MAX个字符，
 * 并且以null终止的字节字符串
 */

size_t size = strlen(secret);
char *newSecret = NULL;
newSecret = (char *)malloc(size + 1);
if (newSecret == NULL) {
    ... // 错误处理
} else {
    errno_t ret = strcpy_s(newSecret, size + 1, secret);
    ... // 处理 ret

    ... // 处理 newSecret...

    free(newSecret);
    newSecret = NULL;
}
...

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000103&navid=NVI1000001214
