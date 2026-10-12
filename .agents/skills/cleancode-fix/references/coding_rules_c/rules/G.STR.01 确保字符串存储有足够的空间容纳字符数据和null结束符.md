# G.STR.01 确保字符串存储有足够的空间容纳字符数据和null结束符

- **规则ID**：58fa3cc7-28e1-41e0-aa1c-a0cf23a7932b
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

将数据复制到不足以容纳数据的缓冲区，会导致缓冲区溢出。缓冲区溢出经常发生在字符串操作中。为了避免这种错误，截断拷贝的数据以限制字符串的字节长度是一种防御方法，但是最好的措施是确保目的缓冲区的大小足以容纳复制数据和null结束符。当字符串存储在堆空间时，确保分配内存时已分配了足够的空间。

部分字符串处理函数由于设计时安全考虑不足，或者存在一些隐含的目的缓冲区长度要求，容易被误用，导致缓冲区写溢出。此类典型函数包括不在C标准库函数中的itoa()，realpath()函数。

**【正确示例】**

```
【正例】
使用安全函数实现整数转换为10进制形式的字符串。

int num = ...
char str[16]; // 有时会考虑字节对齐定义冗余的长度，这里选择了16
int ret = sprintf_s(str, sizeof(str), "%d", num);
...  // 处理错误
【正例】
可以将realpath的第二个参数传入NULL, 以让系统自动分配合适的内存。

char *resolvedPath = NULL;

resolvedPath = realpath(path, NULL);
if (resolvedPath == NULL) {
    ... // 处理错误
}
...
if (resolvedPath != NULL) {
    free(resolvedPath);
    resolvedPath = NULL;
}
...

【正例】
如下代码示例中，在对外部数据进行解析并将内容保存到name中，考虑了name的大小：

int ProcessMessage(unsigned char *msg, size_t length)
{
    ...
    char name[MAX_NAME];
    size_t i = 0;
    // 必须考虑msg不包含预期的字符'
'
    while (i < length &&
           msg[i] != '\0' &&
           msg[i] != '
' &&
           i < MAX_NAME - 1) { // 使用 MAX_NAME - 1 保留结束符空间
        name[i] = msg[i];
        i++;
    }
    name[i] = '\0';
    ...
}

【正例】（差一错误）
如下代码示例中，修改了循环条件，避免差一错误导致的写越界。

...
char dest[ARRAY_SIZE];
char src[ARRAY_SIZE];
...
size_t i;
for (i = 0; src[i] != '
' && i < ARRAY_SIZE - 1; i++) {
    dest[i] = src[i];
}
dest[i] = '\0';

【正例】（fgets函数）
如下代码示例中，fgets函数从流中读取到数组的字符数最多不超过第二个参数减一，并保证目标字符串有’\0’结束符，因此不会造成缓冲区溢出。

#define BUFFER_SIZE 128

char buf[BUFFER_SIZE];
...
if (fgets(buf, sizeof(buf), stdin) == NULL) {
    ... // 错误处理
}
... // 继续处理换行符等
fgets函数不是gets函数的严格替代品，这是因为fgets函数会保留换行符（如果读到的话），也可能返回一个不完整的行。使用fgets函数安全地处理太长而无法保存在目标数组中的行是可能的，但是由于性能原因，不建议这么做。

【正例】（gets_s函数）

gets_s函数最多从stdin流读取指定数量 - 1个字符到目标数组，丢弃换行符并保证有’\0’结束符。 参考C11标准附录K中的描述。
如下代码示例中，使用gets_s读取数据，避免缓冲区溢出：

#define BUFFER_SIZE 128

char buf[BUFFER_SIZE];
if (gets_s(buf, sizeof(buf)) == NULL) {
    ... // 错误处理
}
【正例】(getchar函数)

如下代码示例中，添加了校验代码。当count == BUFFERSIZE - 1时，字符不会再复制到buf，并为结束符留出空间。循环将继续读取字符值直到遇到换行或文件结束为止：

#define BUFFER_SIZE 128

char buf[BUFFER_SIZE];
size_t count = 0;
int ch;

while ((ch = getchar()) != '
' && ch != EOF) {
    if (count < sizeof(buf) - 1) {
        buf[count] = (char)ch;
        count++;
    }
    ...
}
buf[count] = '\0';  // 设置字符串结束符
...

【正例】(scanf函数)
如下代码示例中，调用scanf_s函数以避免缓冲区溢出：

#define BUFFER_SIZE 128

char buf[BUFFER_SIZE];
if (scanf_s("%s", buf, sizeof(buf)) != 1) {
    ... // 错误处理
}
... // 函数实现其它部分

【正例】(strcpy)
复制环境变量时限制其长度，避免出现缓冲区溢出：

#define MAX_ENV_LENGTH 256

char buff[MAX_ENV_LENGTH];
char *editor = getConfig("EDITOR");
if (editor == NULL) {
    ...
} else {
    if (strcpy_s(buff, sizeof(buff), editor) ！= EOK) {
        ... // 错误处理
    }
}
...

【正例】(sprintf函数)

一个解决方案是使用安全函数sprintf_s替代sprintf函数，避免出现缓冲区溢出：

#define MAX_NAME_LEN 128

char filename[MAX_NAME_LEN];
int ret = sprintf_s(filename, sizeof(filename),"%s.txt", name);
if (ret < 0) {
     ... // 错误处理
}
...

```
**【错误示例】**

```
【反例】(itoa)
有些函数如itoa(), realpath()需要在对传入的缓冲区指针位置进行写入操作，但函数并没有提供缓冲区长度。因此，在调用这些函数前，必须提供足够的缓冲区。
如下代码示例中，试图将数字转为字符串，但是目标存储空间的预留长度不足：

int num = ...
char str[8];
itoa(num, str, 10);  // 10进制整数的最大存储长度是12个字节

【反例】(realpath)
如下代码示例中，试图将路径规范化，但是目标存储空间的长度不足：

#define MAX_PATH_LEN 100
char  resolvedPath[MAX_PATH_LEN];

/*
 * realpath函数的存储缓冲区长度是由PATH_MAX常量定义，
 * 或是由_PC_PATH_MAX系统值配置的，通常都大于100字节
 */
char *res = realpath(path, resolvedPath);
...

【反例】
如下代码示例中，在对外部数据进行解析并将内容保存到name中，未考虑name的大小：

int ProcessMessage(unsigned char *msg, size_t length)
{
    ...
    char name[MAX_NAME];
    size_t i = 0;
    // 必须考虑msg不包含预期的字符'
'
    while (i < length &&
           msg[i] != '\0' &&
           msg[i] != '
') {
        name[i] = msg[i];
        i++;
    }
    name[i] = '\0';
    ...
}

【反例】（差一错误）
如下代码示例中，展现了一个差一错误。代码中的循环将数据从src复制到dest。但是因为循环没有考虑’\0’结束符，它可能错误的写入dest缓冲区结束位置之后的一个字节。

...
char dest[ARRAY_SIZE];
char src[ARRAY_SIZE];
...
size_t i;
for (i = 0; src[i] != '
' && i < ARRAY_SIZE; i++) {
    dest[i] = src[i];
}
dest[i] = '\0'; // 不符合：越界写了一个字节

【反例】（gets函数）
gets函数在C99技术勘误3中被弃用，从C11标准中删除，它本是不安全的，绝不应该使用，因为它没有提供任何控制从stdin读取缓冲区数据量的办法。
如下代码示例中，假设gets函数不会读取超过(BUFFER_SIZE - 1)个字符，但是这是个无效的假设，可能造成缓冲区溢出。
gets函数从stdin中读取字符写入目标数组，直到遇到文件结束符或换行符结束，并将换行符丢弃，在读入数组的最后一个字符后面写入’\0’结束符。

#define BUFFER_SIZE 128

char buf[BUFFER_SIZE];
if (gets(buf) == NULL) {
    ... // 错误处理
}


【反例】(getchar函数)

一次读取一个字符提供了控制行为的更大灵活性，但是需要附加的性能开销。如下代码示例中，一次读一个字符直到遇到文件结束或换行符为止，丢弃换行符，并在最后一个读到的字符之后添加’\0’结束符，但是这段代码存在缓冲区溢出风险，没有校验指针是否超出了buf的有效范围：

#define BUFFER_SIZE 128

char buf[BUFFER_SIZE];
char *p = buf;
int ch;

while ((ch = getchar()) != '
' && ch != EOF) {
    *p = (char)ch;
    p++;
}
*p = '\0';
...

【反例】(scanf函数)
如下代码示例中，scanf函数调用可能造成写入到字符数组buf之外：

#define BUFFERSIZE 128

char buf[BUFFER_SIZE];
if (scanf("%s", buf) != 1) {
    ... // 错误处理
}
... // 函数实现其它部分
【反例】(strcpy)

#define MAX_ENV_LENGTH 256

char buff[MAX_ENV_LENGTH];
char *editor = getConfig("EDITOR");
if (editor == NULL) {
    ...
} else {
    strcpy(buff, editor);
}
...

【反例】(sprintf函数)

在如下代码示例中，name引用一个外部字符串；它可能来自用户输入、文件系统或者网络。程序从这个字符串构造一个文件名，准备打开该文件：

#define MAX_NAME_LEN 128

char filename[MAX_NAME_LEN];
sprintf(filename, "%s.txt", name);
...

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000103&navid=NVI1000001158
