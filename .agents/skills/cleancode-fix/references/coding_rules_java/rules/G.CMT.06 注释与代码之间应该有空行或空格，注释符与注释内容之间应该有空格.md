# G.CMT.06 注释与代码之间应该有空行或空格，注释符与注释内容之间应该有空格

- **规则ID**：af5d6fca-7bc7-4d09-a803-4f61d1b64554
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

注释与代码之间、注释符与注释信息之间应该合理通过空行、空格进行分隔，这样可保持代码格式更加清晰。

-  类级成员（一般是类或接口中的属性、方法，嵌套类/内部类依此类推），注释与上面的代码之间加一个空行，但是如果上面已经是本范围（一般是个大括号），则不用加空行。

- 非public非protected的方法，命名无法表达的信息，应该加注释辅助说明，方法头注释统一放在方法声明或定义上方。

- 在方法内部（语句级），注释与上面的代码之间可以考虑加一个空行，以便更加清晰，也可以不用加空行。

**【正确示例】**

```
##### 场景1：类级成员（一般是类或接口中的属性、方法，嵌套类/内部类依此类推），注释与上面的代码之间加一个空行，但是如果上面已经是本范围（一般是个大括号），则不用加空行。

  ```java
  public interface Example {
      /**
       * 成员变量注释 
       */      
      String SOME_FIELD = ...;
	  
      /**
       * 成员变量注释
       */
      String OTHER_FIELD = ...;
	  
	  /**
	   * bar 在方法内部（语句级），注释与上面的代码之间可以考虑加一个空行，以便更加清晰
       *
       * @return int
       * @throws ProblemException ProblemException
       */
      default int bar() throws ProblemException {
          // 局部变量变量注释          
          var aVar = ...;
          
          // 方法注释
          doSomething();
      }

	  /**
	   * bar 在方法内部（语句级），注释与上面的代码之间也可以不加空行
       *
       * @return int
       * @throws ProblemException ProblemException
       */
	  default int bar1() throws ProblemException {
          // 局部变量注释          
          var aVar = ...;
          // 方法注释
          doSomething();
      }
  }
  ```
##### 场景2：代码右边的注释，与代码之间，至少留1空格，注释字符(//)与注释文字之间留1空格。

  ```java
  int foo = 100; // 变量注释
  int bar = 200; // 变量注释
  ```


```
**【错误示例】**

```
##### 场景1：类级成员（一般是类或接口中的属性、方法，嵌套类/内部类依此类推），注释与上面的代码之间加一个空行，但是如果上面已经是本范围（一般是个大括号），则不用加空行。
- 错误示例：

  ```java
  public interface Example {
      /**
       * 成员变量注释 
       */
      String SOME_FIELD = ...;
      /**
       * 成员变量注释，【不符合】类属性注释与上面的代码之间没加空行
       */
      String OTHER_FIELD = ...;
	  /**
       * bar，【不符合】方法注释与上面的代码之间没加空行
       *
       * @return int
       * @throws ProblemException ProblemException
       */
      default int bar() throws ProblemException {
          doSomething();
      }
  }
  ```
##### 场景2：代码右边的注释，与代码之间，至少留1空格，注释字符(//)与注释文字之间留1空格。
- 错误示例：

  ```java
  int foo = 100;// 变量注释，【不符合】注释与代码之间没有留空格
  int bar = 200; //变量注释，【不符合】注释字符(//)与注释文字之间没有留空格
  ```


```
**【修复建议】**

推荐使用工具自动对代码进行格式化处理，建议使用[HiCode的codecheck插件](https://hicode.huawei.com/#/docs/IDE%E6%8F%92%E4%BB%B6/CodeCheck)的检查和修复功能，或使用开源项目[EasyCode](https://openx.huawei.com/EasyCode/overview)中的代码格式化模板对代码进行格式化处理。
