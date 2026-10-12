# SecJ_Ignore_Returned_Value

- **规则ID**：6eae5343-0197-4c8e-adab-d5902c2ef478
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

检测方法的返回值被忽略。



返回值被忽略通常是错误地实现，会导致程序无法发现意外状况和情况。

**【正确示例】**

```
```java
public void deleteFileGood() {
    File someFile = new File("someFileName.txt");
    if (someFile.delete()) { // [GOOD] delete() 返回是否正确删除，而这里通常处理返回值对之进行了处理。
        logger.info("delete success");
        // ...
    }else{
        logger.info("delete fail");
        // ...
    }
}
```

```
**【错误示例】**

```
```java
public void deleteFileBad() {
    File someFile = new File("someFileName.txt");
    /* [BAD] 可能有问题： delete 可能删除失败，返回 false，但这里如果忽略了返回值，就无从得知了 */
    someFile.delete();
}
```

```
**【修复建议】**

总是处理方法的返回值。
