# G.FIO.01 使用外部数据构造的文件路径前必须进行校验，校验前必须对文件路径进行规范化处理

- **规则ID**：dbd3ce9d-913c-45c2-8b35-88aedbf9f9dc
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

文件路径来自外部数据时，必须对其合法性进行校验，否则可能会产生路径遍历（Path Traversal）漏洞。文件路径有多种表现形式，如绝对路径、相对路径，路径中可能会含各种链接、快捷方式、影子文件 等，这些都会对文件路径的校验产生影响，所以在文件路径校验前要对文件路径进行规范化处理，使用 规范化的文件路径进行校验。对文件路径的规范化处理必须使用 getCanonicalPath() ，禁止使用 getAbsolutePath() （该方法无法保证在所有的平台上对文件路径进行正确的规范化处理）

**【正确示例】**

```
使用外部输入的fileName构造文件路径后，先对文件路径进行规范化，然后用规范化 的文件路径进行校验，满足条件后执行文件读写操作。这样可以有效避免路径遍历之类的风险。
public void doSomething() {
    File file = new File(HOME_PATH, fileName);
    try {
        String canonicalPath = file.getCanonicalPath();
        if (!validatePath(canonicalPath)) {
            throw new IllegalArgumentException("Path Traversal vulnerability!");
        }
        // ... 对文件进行读写等操作
    } catch (IOException ex) {
        throw new IllegalArgumentException("An exception occurred ...", ex);
    }
}
private boolean validatePath(String path) {
    if (path.startsWith(HOME_PATH)) {
        return true;
    } else {
        return false;
    }
}

```
**【错误示例】**

```
代码中fileName来自外部输入，直接用fileName的值与固定路径进行拼接，作为实际访问文件的路径，在访问文件之前通过 validatePath 检查了拼接的路径是否在固定目录下，但是攻击者可以通过../这样的路径方式，访问HOME_PATH之外的任意文件。
public void doSomething() {
    File file = new File(HOME_PATH, fileName);
    String path = file.getAbsolutePath();
    if (!validatePath(path)) {
        throw new IllegalArgumentException("Path Traversal vulnerabilities may exist！");
    }
    // ... 对文件进行读写等操作
}
private boolean validatePath(String path) {
    if (path.startsWith(HOME_PATH)) {
        return true;
    } else {
        return false;
    }
}

```
**【修复建议】**

在文件验证之前，使用getCanonicalPath()而非getAbsolutePath()获取文件路径
