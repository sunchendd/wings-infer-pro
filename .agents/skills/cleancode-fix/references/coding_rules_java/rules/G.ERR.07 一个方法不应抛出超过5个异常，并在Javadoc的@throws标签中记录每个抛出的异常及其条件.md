# G.ERR.07 一个方法不应抛出超过5个异常，并在Javadoc的@throws标签中记录每个抛出的异常及其条件

- **规则ID**：566261ff-cb98-4c74-a17a-bb1169233bef
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

方法抛出过多的异常，会增加上层调用方法中的异常处理的工作，同时也表明方法承担了过多的职责，推荐一个方法最多抛出maxThrowNum（默认值为5，支持动态配置）类异常，包括受检异常和运行时异常。方法抛出的异常中应该避免存在继承关系，存在继承关系时，仅保留父类异常。

**【正确示例】**

```
##### 场景1：
- 修复示例：减少throw的异常种类

  ```java
  private static byte[] getNewBytes(byte[] password, byte[] tmpByte) throws NoSuchAlgorithmException, NoSuchPaddingException { 
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：方法throw的异常种类超过5种

  ```java
  private static byte[] getNewBytes(byte[] password, byte[] tmpByte) throws NoSuchAlgorithmException, NoSuchPaddingException,         
      InvalidKeyException,InvalidAlgorithmParameterException, IllegalBlockSizeException, BadPaddingException { 
      ...
  }
  ```


```
**【修复建议】**

方法抛出异常的类型超过maxThrowNum时，建议对方法进行合理拆分或对异常进行封装。
