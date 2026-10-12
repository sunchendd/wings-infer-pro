# G.ERR.06 在catch块中抛出新异常时，避免丢失原始异常信息

- **规则ID**：6293beae-c00e-4a68-8674-6a75a9a58a7e
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

在catch代码块中更改异常类型时，如果只是使用原始异常中的message（originalException.getMessage()）或使用新的错误描述信息构造新异常，可能会导致原始异常中的有价值的信息丢失，例如异常类型、调用堆栈等信息，增加问题定位的难度。



为了保证不丢失异常信息，可以采取以下策略：

1. **包含原始异常信息**：在构造新异常时，将原始异常作为构造函数的参数传递，如 `throw new CustomException("新的错误描述", originalException);`。这样，新异常会包含原始异常的堆栈跟踪，便于追踪问题源头。

2. **记录原始异常到日志**：在抛出新异常之前，先将原始异常的详细信息记录到日志中。例如 `LOG.error("新错误描述", originalException);`。这样即使新异常中不包含全部原始异常信息，也可以通过日志获取。

3. **处理敏感信息**：如果原始异常包含敏感信息，应在记录日志或传递给新异常之前进行匿名化或脱敏处理，以保护信息安全。



遵循这些做法，可以在保证异常处理逻辑清晰的同时，也保留了足够的调试信息。

**【正确示例】**

```
##### 场景1：丢失原始异常信息。
- 修复示例1：在新抛出的异常中放入原始异常信息ex：
```java
try {
    new File("").createNewFile();
} catch (IOException ex) {
    throw new CustomException("file not found", ex);// 抛出异常信息携带原始异常
}
```
- 修复示例2：原始异常记录日志后，再抛出新异常：
```java
try {
    new File("").createNewFile();
} catch (IOException ex) {
    LOG.error("file not found: " + ex);// 日志中打印出原始异常
    throw new CustomException("file not found");
}

```
- 修复示例3：原始异常存在敏感信息的，先清理敏感信息后再记录日志，并抛出新异常：
 ```java
 try {
     new File("").createNewFile();
 } catch (IOException ex) {
     LOG.error("file not found: " + filterFileSensitiveInfo(ex)); // 日志中打印出清理敏感信息后的原始异常信息
     throw new CustomException("file not found");
 }
 
 /**
  * 过文件系统中的滤敏感信息
  *
  * @param message message
  * @return 脱敏后的message
  */
 public static String filterFileSensitiveInfo(IOException ex) {
     String message = ex.getMessage();
     if (message == null || message.isEmpty()) {
         return "";
     }
     // 移除敏感路径信息 
     message = message.replaceAll("业务校验正则（产品依据业务自行决定)", "[FILTERED_PATH]");
     return message;
 }
 ```

```
**【错误示例】**

```
##### 场景1：丢失原始异常信息。
- 错误示例：原始异常ex没有打印到日志中，也没有被包含在新抛出的异常中。

```java
try {
    new File("").createNewFile();
} catch (IOException ex) {
    throw new CustomException("file not found");
}
```

```
**【修复建议】**

修复方法1：新异常中要包含原始异常中的所有信息（敏感信息可先进行匿名化处理）；

修复方法2：原始异常先记录到日志（敏感信息先脱敏处理）中，再抛出新构造的异常（仅包含部分原始异常信息）。
