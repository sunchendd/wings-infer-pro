# G.FIL.02 使用文件路径前必须进行规范化并校验

- **规则ID**：737ea286-d7f7-4926-a449-f19c27477b9c
- **更新时间**：2025-03-25 19:23:47

---

**【问题级别】**

一般

**【描述】**

当文件路径来自外部数据时，必须对其做合法性校验，如果不校验，可能造成系统文件的被任意访问。但是禁止直接对其进行校验，正确做法是在校验之前必须对其进行路径规范化处理。这是因为同一个文件可以通过多种形式的路径来描述和引用，例如既可以是绝对路径，也可以是相对路径；而且路径名、目录名和文件名可能包含使校验变得困难和不准确的字符（如：“.”、“..”）。此外，文件还可以是符号链接，这进一步模糊了文件的实际位置或标识，增加了校验的难度和校验准确性。所以必须先将文件路径规范化，从而更容易校验其路径、目录或文件名，增加校验准确性。



因为规范化机制在不同的操作系统和文件系统之间可能有所不同，所以最好使用符合当前系统特性的规范化机制。例如：在linux下，使用realpath函数，在windows下，使用PathCanonicalize函数进行文件路径的规范化。

**【正确示例】**

```
char *realpathRes = NULL;

...

// 在校验之前，先对inputFilename做规范化处理
realpathRes = realpath(inputFilename, NULL);
if (realpathRes == NULL) {
    ... // 规范化的错误处理
}

// 规范化以后对路径进行校验
if (!verify_file(realpathRes) {
    ... // 校验的错误处理
}

// 使用
if (fopen(realpathRes, "w") == NULL) {
    ... // 实际操作的错误处理
}

...

free(realpathRes);
realpathRes = NULL;
...
【正例】
根据我们的实际场景，我们还可以采用的第二套解决方案，说明如下：
如果PATH_MAX被定义为 limits.h 中的一个常量，那么使用非空的resolved_path调用realpath()也是安全的。
在本例中realpath()函数期望resolved_path引用一个字符数组，该字符数组足够大，可以容纳规范化的路径。
如果定义了PATH_MAX，则分配一个大小为PATH_MAX的缓冲区来保存realpath()的结果。正确代码示例如下：

【正例】
规范化文件名是具有一定难度的，因为这需要了解底层文件系统。
POSIX realpath()函数可以帮助将路径名转换为规范形式。参考信息技术标准-POSIX®，基本规范第7期[IEEE std 1003.1：2013]：

该realpath()函数应从所指向的路径名派生一个filename的绝对路径名，两者指向同一文件，绝对路径其文件名不涉及“ .”，“ ..”或符号链接。
在规范化路径之后，还必须执行进一步的验证，例如确保两个连续的斜杠或特殊文件不会出现在文件名中。有关如何执行路径名解析的更多详细信息，请参见[IEEE Std 1003.1: 2013]第4.12节“路径名解析”。
使用realpath()函数有许多需要注意的地方，详细可以翻看Linux程序员手册。
在了解了以上原理之后，对上面的错误代码示例，我们采用如下解决方案：
char *realpathRes = NULL;
char *canonicalFilename = NULL;
size_t pathSize = 0;

...

pathSize = (size_t)PATH_MAX;

if (VerifyPathSize(pathSize) == true) {
    canonicalFilename = (char *)malloc(pathSize);

    if (canonicalFilename == NULL) {
        ... // 错误处理
    }

    realpathRes = realpath(inputFilename, canonicalFilename);
}

if (realpathRes == NULL) {
    ... // 错误处理
}

if (VerifyFile(realpathRes) == false) {
    ... // 错误处理
}

if (fopen(realpathRes, "w") == NULL ) {
    ... // 错误处理
}

...

free(canonicalFilename);
canonicalFilename = NULL;
...
【正例】
正确的做法是，对路径进行规范化后，再判断路径是否是本程序所认为的合法的路径：

char *filename = GetMsgFromRemote();
...
sprintf_s(untrustPath, sizeof(untrustPath), "/tmp/%s", filename);
char path[PATH_MAX];
if (realpath(untrustPath, path) == NULL) {
    ... // 处理错误
}
if (!IsValidPath(path)) {    // 检查文件的位置是否正确
    ... // 处理错误
}
char *text = ReadFileContent(path);

```
**【错误示例】**

```
【反例】
在此错误的示例中，inputFilename包含一个源于受污染源的文件名，并且该文件名已打开以进行写入。在使用此文件名操作之前，应该对其进行验证，以确保它引用的是预期的有效文件。
不幸的是，inputFilename引用的文件名可能包含特殊字符，例如目录字符，这使验证变得困难，甚至不可能。而且，inputFilename中可能包含可以指向任意文件路径的符号链接，即使该文件名通过了验证，也会导致该文件名是无效的。
这种场景下，对文件名的直接验证即使被执行也是得不到预期的结果，对fopen()的调用可能会导致访问一个意外的文件。
if (!verify_file(inputFilename) {    // 没有对inputFilename做规范化，直接做校验
    ... // 错误处理
}

if (fopen(inputFilename, "w") == NULL) {
    ... // 错误处理
}

【反例】
下面的代码场景是从外部获取到文件名称，拼接成文件路径后，直接对文件内容进行读取，导致攻击者可以读取到任意文件的内容：

char *filename = GetMsgFromRemote();
...
int ret = sprintf_s(untrustPath, sizeof(untrustPath), "/tmp/%s", filename);
...
char *text = ReadFileContent(untrustPath);

```
**【修复建议】**

对输入路径进行标准化处理，windows下可以用PathCanonicalize()函数，linux下可以使用realpath()函数。
