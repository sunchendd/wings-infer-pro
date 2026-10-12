# G.TYP.02-TS 接口、类中的成员声明应该有一致的顺序

- **规则ID**：4c378809-96e0-42f5-b411-85541b3df5f7
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

一致的成员声明顺序可以使接口、类更易于阅读和编辑。

**【正确示例】**

```
##### 场景1：成员声明
- 修复示例：和推荐的成员声明顺序保持一致：Signature、Field、Getter、Setter、Constructor、Method。
```javascript
interface Foo {
  // Signature
  [key: string]: number; 
  
  // Field
  name: string;
  age: number;
  weight: number;
	
  // Constructor
  new (): Bar;
  (): Baz;

  // Getter
  get fullName(): string;

  // Setter
  set fullName(value: string): void; 

  // Method
  getName(): string;
  getAge(): number;
  getWeight(): number;
}
```

```
**【错误示例】**

```
##### 场景1：成员声明
- 错误示例：成员声明顺序是Field、Constructor、Method、Getter、Setter、Signature。跟推荐的声明顺序不一致。
```javascript
interface Foo {
  // Field
  name: string;
  age: number;
  weight: number;
	
  // Constructor
  new (): Bar;
  (): Baz;
	
  // Method
  getName(): string;
  getAge(): number;
  getWeight(): number;

  // Getter
  get fullName(): string;

  // Setter
  set fullName(value: string): void; 

  // Signature
  [key: string]: number;
}
```

```
**【修复建议】**

推荐的成员声明顺序是：



1. Signature 



2. Field 

    2.1 Static Field

    2.2 Decorated Field

    2.3 Instance Field

    2.4 Abstract Field

    2.5 Field（无任何修饰）



3. Constructor 



4. Method

    4.1 Static Method

    4.2 Decorated Method

    4.3 Instance Method

    4.4 Abstract Method

    4.5 Method（无任何修饰）



其中每种成员都遵循 public -> protected -> private 的顺序。



示例：

```ts

abstract class ExampleOrder {

  // 索引签名（signature）

  [key: string]: any;



  // 字段（Fields）---------------------------------------------------------------

  // 静态字段（Static Fields）

  public static staticPublicField: string; // 公共静态字段

  protected static staticProtectedField: string; // 受保护的静态字段

  private static staticPrivateField: string; // 私有静态字段



  // 装饰字段（Decorated Fields）

  @Log() public decoratedPublicField: string; // 公共装饰字段

  @Log() protected decoratedProtectedField: string; // 受保护的装饰字段

  @Log() private decoratedPrivateField: string; // 私有装饰字段



  // 实例字段（Instance Fields）

  public instancePublicField: string; // 公共实例字段

  protected instanceProtectedField: string; // 受保护的实例字段

  private instancePrivateField: string; // 私有实例字段



  // 抽象字段（Abstract Fields）

  public abstract abstractPublicField: string; // 公共抽象字段

  protected abstract abstractProtectedField: string; // 受保护的抽象字段



  // 通用字段分类（General Field Categories）

  public publicField: string; // 公共字段（由 public-instance-field 覆盖）

  static staticField: string; // 静态字段（由 public-static-field 覆盖）

  private privateField: string; // 私有字段（由 private-instance-field 覆盖）



  // 构造函数（Constructors）-----------------------------------------------------

  public constructor() {} // 公共构造函数

  protected protectedConstructor() {} // 受保护的构造函数

  private privateConstructor() {} // 私有构造函数



  // 方法（Methods）-------------------------------------------------------------

  // 静态方法（Static Methods）

  public static staticPublicMethod() {} // 公共静态方法

  protected static staticProtectedMethod() {} // 受保护的静态方法

  private static staticPrivateMethod() {} // 私有静态方法



  // 装饰方法（Decorated Methods）

  @Log() public decoratedPublicMethod() {} // 公共装饰方法

  @Log() protected decoratedProtectedMethod() {} // 受保护的装饰方法

  @Log() private decoratedPrivateMethod() {} // 私有装饰方法



  // 实例方法（Instance Methods）

  public instancePublicMethod() {} // 公共实例方法

  protected instanceProtectedMethod() {} // 受保护的实例方法

  private instancePrivateMethod() {} // 私有实例方法



  // 抽象方法（Abstract Methods）

  public abstract abstractPublicMethod(): void; // 公共抽象方法

  protected abstract abstractProtectedMethod(): void; // 受保护的抽象方法



  // 通用方法分类（General Method Categories）

  public publicMethod() {} // 公共方法（由 public-instance-method 覆盖）

  static staticMethod() {} // 静态方法（由 public-static-method 覆盖）

  private privateMethod() {} // 私有方法（由 private-instance-method 覆盖）

}

```
