# G.TYP.01 进行数值运算时，避免整数溢出

- **规则ID**：468a5d09-79d1-4c43-8a7e-09669b5fc0e8
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

在进行数值运算过程中，确保运算结果在特定的整数类型的数据范围内，避免溢出，导致非预期的结果。



内置的整数运算符不会以任何方式来标识运算结果的上溢或下溢。常见的加、减、乘、除都可能会导致整数溢出。另外，Java数据类型的合法取值范围是不对称的（最小值的绝对值比最大值大1），所以对最小值取绝对值（java.lang.Math.abs()）时，也会导致溢出。



对于整数溢出问题，可以通过先决条件检测、使用Math类的安全方法、向上类型转换或者使用BigInteger等方法进行规避。

**【正确示例】**

```
##### 场景1：使用int类型统计文件大小
- 修复示例：使用long类型变量统计总文件大小，可以有效避免出现整数溢出问题。
 ```java
public void unzip(FileInputStream zipFileInputStream, String dir) throws IOException {
    try (ZipInputStream zis = new ZipInputStream(zipFileInputStream)) {
        long totalFileSize = 0L;
        int readSize = 0;
        while ((entry = zis.getNextEntry()) != null) {
            ...
            while ((readSize = zis.read(buf)) != -1) {
                totalFileSize += readSize; // 使用long型统计文件总大小，可避免出现整数溢出问题
                if(totalFileSize >= MAX_TOTAL_FILE_SIZE) {
                    ...
                }
            ...
```


```
**【错误示例】**

```
##### 场景1：使用int类型统计文件大小
- 错误示例：在统计zip文件中解压文件的总大小时使用了int类型的变量，由于int类型的上限为2G，当统计的文件总大小超过2G时将发生整数溢出。

```java
public void unzip(FileInputStream zipFileInputStream, String dir) throws IOException {
    try (ZipInputStream zis = new ZipInputStream(zipFileInputStream)) {
        int totalFileSize = 0;
        int readSize = 0;
        while ((entry = zis.getNextEntry()) != null) {
            ...
            while ((readSize = zis.read(buf)) != -1) {
                totalFileSize += readSize; // 使用int型变量统计文件总大小，容易出现整数溢出问题
                if(totalFileSize >= MAX_TOTAL_FILE_SIZE) {
                    ...
                }
            ...
```


```
**【修复建议】**

对于整数溢出问题，可以通过先决条件检测、使用Math类的安全方法、向上类型转换或者使用BigInteger等方法进行规避。
