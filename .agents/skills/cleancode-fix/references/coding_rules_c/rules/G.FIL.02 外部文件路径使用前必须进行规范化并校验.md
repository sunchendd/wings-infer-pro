# G.FIL.02 外部文件路径使用前必须进行规范化并校验

- **规则ID**：5d027a21-4a28-4e04-a8de-b23a649378d2
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

外部文件路径不可信，如果不规范外部文件路径，攻击者就有机会通过恶意构造文件路径进行文件的越权访问；如果不校验外部文件路径，可能造成系统文件的被任意访问，出现安全风险。

因此，外部文件路径使用前必须进行规范化并校验。

**【正确示例】**

```
 ### 场景1：外部文件路径未规范化。

 - 修复示例1：先对filename规范化，再校验规范化后的文件路径是否是本程序所认为的合法的路径。

 ```c
 char *filename = GetMsgFromRemote();
 
 // 符合：规范化
 char *canonicalPath = realpath(filename, NULL);
 if (canonicalPath == NULL) {
     ... // 错误处理
 }
 
 // 校验
 if (!IsValidPath(canonicalPath)) {
     ... // 错误处理
 }
 
 // 使用正确的文件路径
 if (fopen(canonicalPath, "w") == NULL) {
     ... // 错误处理
 }
 
 ...
 free(canonicalPath);
 canonicalPath = NULL;
 ...
 ```

 - 修复示例2：先对filename规范化，再校验规范化后的文件路径是否是本程序所认为的合法的路径。
 ```c
 char *filename = GetMsgFromRemote();
 
 char *canonicalPath = (char *)malloc(PATH_MAX);
 ... // 返回值检查及初始化，略
 
 // 符合：规范化
 if (realpath(filename, canonicalPath) == NULL) {
     ... // 错误处理
 }
 
 if (!IsValidPath(canonicalPath)) {
     ... // 错误处理
 }
 
 if (fopen(canonicalPath, "w") == NULL ) {
     ... // 错误处理
 }
 
 ...
 free(canonicalPath);
 canonicalPath = NULL;
 ...
 ```

  ### 场景2：新建文件，需要规范化文件目录。

 - 修复示例：先对文件目录进行规范化，再新建文件
 ```c
 int GoodCase01(char* dir)
 {
     char* canonicalPath = realpath(dir, NULL);
     if (canonicalPath == NULL) {
         ... // 错误处理
     }
     char filename[PATH_MAX];
     int ret = snprintf_s(filename, PATH_MAX, PATH_MAX - 1, "%s/a.cpp", canonicalPath);
     if (ret != -1) {
         ... // 错误处理
     }
     /* 符合:  */
     if (fopen(filename, "w") == NULL) {
         ... // 错误处理
     }
     
     ...
     free(canonicalPath);
     canonicalPath = NULL;
     ...
 }
 ```

```
**【错误示例】**

```
 ### 场景1：外部文件路径未规范化。

 - 错误示例：

 ```c
 char *filename = GetMsgFromRemote();  // filename直接来自外部
 
 if (!IsValidFile(filename)) {  // 不符合：未做规范化，直接做校验
     ... // 错误处理
 }
 
 if (fopen(filename, "w") == NULL) {
     ... // 错误处理
 }
 ...
 ```

  ### 场景2：新建文件，需要规范化文件目录。

 - 错误示例：
 ```c
 int BadCase01(char* dir)
 {
     char filename[PATH_MAX];
     int ret = snprintf_s(filename, PATH_MAX, PATH_MAX - 1, "%s/a.cpp", dir);
     if (ret == -1) {
         ... // 错误处理
     }
     /* 不符合:  */
     if (fopen(filename, "w") == NULL) {
         ... // 错误处理
     }
     ...
 }
 
 ```

```
**【修复建议】**

外部文件路径使用前，按顺序执行如下两个步骤：

**1、文件路径规范化**：因为规范化机制在不同的操作系统和文件系统之间可能有所不同，所以最好使用符合当前系统特性的规范化机制，如：在linux下，使用`realpath()`等方式，在windows下，使用`PathCanonicalize()`、`PathCchCanonicalize()`等方式。

**2、文件路径校验**：针对规范化后的文件路径进行校验。常用的校验方式是保证操作的文件在预期目录下。
