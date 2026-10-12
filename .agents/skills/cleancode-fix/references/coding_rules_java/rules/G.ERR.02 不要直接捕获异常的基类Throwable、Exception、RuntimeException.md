# G.ERR.02 不要直接捕获异常的基类Throwable、Exception、RuntimeException

- **规则ID**：71ed5b6d-7bfd-4cd1-b7d7-722715cbf91c
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

捕获异常的目的是为了将程序从异常状态恢复或对异常进行针对性处理，而如果不加区分的直接捕获基类异常，则会忽略程序抛出的异常类型，无法对各类异常进行有针对性地恢复处理，另外不利于代码的可读性、可维护性。



当程序中的多种异常使用同一逻辑进行处理时，可以用并语法(ExceptionType1 | ... | ExceptionTypeN 变量)来减少重复代码。

**【正确示例】**

```
##### 场景1：直接捕获并处理Exception
- 修复示例： 

  ```java
    try {
        doSomething();
    } catch (IOException  ex) {  //应根据实际情况捕获具体的子异常类
        handleException(ex);
    }
  ```

##### 场景2：对于相同处理逻辑的异常，建议通过并语法(ExceptionType1 | ... | ExceptionTypeN 变量)来减少重复代码
- 修复示例： 

  ```java
    try {
        doSomething();
    } catch (ParseException | IOException ex) {
        handleException(ex);
    } 
  ```

##### 场景3：对于不同的异常ParseException 、IOException分别进行了对应的处理
- 修复示例： 

  ```java
     try {
         doSomething();
     } catch (ParseException  ex) {
         handleParseException(ex);
     } catch (IOException  ex) {
         handleIOException(ex);
     }
  ```

##### 场景4：捕获明确异常后，使用基类异常进行兜底处理
- 修复示例： 

  ```java
     try {
          doSomething();
     } catch (ParseException ex) {
          handleParseException(ex);
     } catch (IOException  ex) {
          handleIOException(ex);
     } catch(Exception ex) {
          handleOtherException(ex);
     }
  ```


```
**【错误示例】**

```
##### 场景1：直接捕获并处理Exception
- 错误示例：直接捕获异常的基类

  ```java
    try {
        doSomething();
    } catch (Exception ex) {
        handleException(ex);
    }
  ```

```
**【修复建议】**

捕获具体的子异常类型，使用语法`(ExceptionType1 | ... | ExceptionTypeN 变量)`合并处理逻辑相同的异常。
