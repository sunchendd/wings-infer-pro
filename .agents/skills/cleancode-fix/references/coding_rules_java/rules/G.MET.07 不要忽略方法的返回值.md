# G.MET.07 不要忽略方法的返回值

- **规则ID**：2bd7fd80-5164-48d3-aea3-fc6157496b40
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

方法调用者应该对方法的返回值进行合理的处理，否则可能因为忽略方法返回值导致安全风险。 资源操作类方法会通过返回值来指示本次操作是否成功（例如File.delete()），这类方法调用后必须根据返回值对资源操作失败的场景进行防护处理。

**【正确示例】**

```
##### 场景1：调用文件操作相关方法。
- 修复示例：

```java
public void deleteFile() {
    File someFile = new File("someFileName.txt");

    // Do something with someFile
    if (!someFile.delete()) {
        // Handle failure to delete the file
        ...
    }
}
```
##### 场景2：String类操作
- 修复示例：

```java
String original = "insecure";
original = original.replace('i', '9');
System.out.println(original); // 输出 9nsecure
```


```
**【错误示例】**

```
##### 场景1：调用文件操作相关方法。
- 错误示例：

```java
public void deleteFile() {
    File someFile = new File("someFileName.txt");

    // Do something with someFile
    someFile.delete();
}
```
##### 场景2：String类操作
- 错误示例：

```java
String original = "insecure";
original.replace('i', '9');
System.out.println(original); // 输出 insecure
```


```
**【修复建议】**

1. 资源操作类方法（例如File.delete()）调用后必须根据返回值对资源操作失败的场景进行防护处理。

2. Java中的String是不可变类型，对于字符串的修改要赋值给新的String变量。
