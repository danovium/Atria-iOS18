// iOS 18 uses NSString grid classes and immutable SBHIconGridSizeClassSizeMap
// objects. Keep these declarations separate from the integer/struct iOS 14 ABI.
#import "Shared.h"
#import "../Manager/ARITweakManager.h"
#import <objc/runtime.h>
#import <math.h>

char ARIOriginalGridDimensionsKey;

@interface NSValue (ARIGridSize18)
+ (instancetype)sbh_valueWithSBHIconGridSize:(SBHIconGridSize)size;
@end

@interface ARIGridSizeMap18 : NSObject
- (instancetype)initWithGridSizeClassSizes:(NSDictionary *)sizes;
- (void)enumerateGridSizesUsingBlock:(void (^)(NSString *, SBHIconGridSize, BOOL *))block;
@end

@interface ARIIcon18 : NSObject
- (NSString *)gridSizeClass;
@end

@interface ARIListModel18 : NSObject
@property (nonatomic, strong) id _atriaOriginalSizeMap18;
@property (nonatomic, strong) id _atriaSizeMap18;
@property (nonatomic, strong) NSString *_atriaSizeMapKey18;
- (SBHIconGridSize)gridSizeWithOptions:(NSUInteger)options;
@end

@interface ARIListView18 : UIView
@property (nonatomic, readonly) NSString *iconLocation;
- (ARIIcon18 *)iconAtCoordinate:(SBIconCoordinate)coordinate metrics:(id)metrics;
- (CGSize)iconImageSizeForGridSizeClass:(NSString *)sizeClass;
- (SBHIconGridSize)iconGridSizeForClass:(NSString *)sizeClass;
- (CGSize)effectiveIconSpacing;
@end

// Scale the system's actual widget footprints so new/unknown classes are kept.
// Clamp to at least one cell and to the page bounds on small custom grids.
static SBHIconGridSize ARIScaleWidget18(SBHIconGridSize size,
                                       SBHIconGridSize systemGrid,
                                       NSUInteger columns, NSUInteger rows) {
    SBHIconGridSize result;
    result.width = (short)MAX(1, MIN(columns, lround((double)size.width * columns / MAX(1, systemGrid.width))));
    result.height = (short)MAX(1, MIN(rows, lround((double)size.height * rows / MAX(1, systemGrid.height))));
    return result;
}

%group Widgets18
%hook ARIListModel18
%property (nonatomic, strong) id _atriaOriginalSizeMap18;
%property (nonatomic, strong) id _atriaSizeMap18;
%property (nonatomic, strong) NSString *_atriaSizeMapKey18;

- (id)gridSizeClassSizesWithOptions:(NSUInteger)options {
    ARIListModel18 *typedSelf = (ARIListModel18 *)self;
    id original = %orig;
    ARITweakManager *manager = [ARITweakManager sharedInstance];
    SBIconListModel *model = (SBIconListModel *)self;
    SBIconListView *listView = [model _atriaListView];
    if(!original || !listView || !IsLocationRoot(model._atriaLocation) ||
       ![manager boolValueForKey:@"dynamicWidgetSizing"]) return original;

    BOOL landscape = (options & 2) != 0;
    NSUInteger columns = [manager intValueForKey:landscape ? @"hs_rows" : @"hs_columns" forListView:listView];
    NSUInteger rows = [manager intValueForKey:landscape ? @"hs_columns" : @"hs_rows" forListView:listView];
    columns = MAX(1, MIN(columns, 127));
    rows = MAX(1, MIN(rows, 127));
    // The provider mutates even the original configuration (including its
    // 127-cell visibility workaround). Use the dimensions captured beforehand.
    SBIconListGridLayoutConfiguration *config = listView._originalLayout.layoutConfiguration;
    NSArray<NSNumber *> *dimensions = objc_getAssociatedObject(config, &ARIOriginalGridDimensionsKey);
    if(dimensions.count != 4) return original;
    SBHIconGridSize systemGrid = {
        .width = [dimensions[landscape ? 2 : 0] shortValue],
        .height = [dimensions[landscape ? 3 : 1] shortValue]
    };
    if(systemGrid.width < 1 || systemGrid.height < 1) return original;
    NSString *key = [NSString stringWithFormat:@"%lu:%lu:%lu:%d:%d", (unsigned long)columns,
                     (unsigned long)rows, (unsigned long)options, systemGrid.width, systemGrid.height];
    if(typedSelf._atriaOriginalSizeMap18 == original && [typedSelf._atriaSizeMapKey18 isEqualToString:key]) {
        return typedSelf._atriaSizeMap18 ?: original;
    }
    NSMutableDictionary *sizes = [NSMutableDictionary dictionary];
    [(ARIGridSizeMap18 *)original enumerateGridSizesUsingBlock:^(NSString *sizeClass, SBHIconGridSize size, BOOL *stop) {
        // iOS 18 also uses non-default classes for enlarged app icons and
        // controls. Override only the four established widget classes.
        if([@[@"SBHIconGridSizeClassSmall", @"SBHIconGridSizeClassMedium",
              @"SBHIconGridSizeClassLarge", @"SBHIconGridSizeClassExtraLarge"] containsObject:sizeClass]) {
            size = ARIScaleWidget18(size, systemGrid, columns, rows);
        }
        sizes[sizeClass] = [NSValue sbh_valueWithSBHIconGridSize:size];
    }];
    id map = [(ARIGridSizeMap18 *)[objc_getClass("SBHIconGridSizeClassSizeMap") alloc] initWithGridSizeClassSizes:sizes];
    typedSelf._atriaOriginalSizeMap18 = original;
    typedSelf._atriaSizeMapKey18 = key;
    typedSelf._atriaSizeMap18 = map;
    return map ?: original;
}
%end

%hook ARIListView18
- (CGPoint)originForIconAtCoordinate:(SBIconCoordinate)coordinate metrics:(SBIconListViewLayoutMetrics *)metrics options:(NSUInteger)options {
    ARIListView18 *list = (ARIListView18 *)self;
    CGPoint origin = %orig;
    if(options || !IsLocationRoot(list.iconLocation)) return origin;
    ARIIcon18 *icon = [list iconAtCoordinate:coordinate metrics:metrics];
    if(![icon isKindOfClass:objc_getClass("SBWidgetIcon")]) return origin;
    NSString *sizeClass = [icon gridSizeClass];
    CGSize imageSize = [list iconImageSizeForGridSizeClass:sizeClass];
    SBHIconGridSize gridSize = [list iconGridSizeForClass:sizeClass];
    CGSize spacing = [list effectiveIconSpacing];
    CGFloat columnWidth = metrics.alignmentIconSize.width + spacing.width;
    // The first coordinate field is the column on iOS 16 and later.
    CGFloat before = columnWidth * (coordinate.row - 1) - spacing.width / 2.0;
    CGFloat centered = metrics.iconInsets.left + before + (columnWidth * gridSize.width - imageSize.width) / 2.0;
    ARITweakManager *manager = [ARITweakManager sharedInstance];
    SBIconListView *listView = (SBIconListView *)self;
    if(isfinite(centered)) origin.x = centered;
    origin.x += [manager floatValueForKey:@"hs_widgetXOffset" forListView:listView];
    origin.y += [manager floatValueForKey:@"hs_widgetYOffset" forListView:listView];
    return origin;
}
%end
%end

static BOOL ARIObjectArgument18(Class cls, SEL selector, unsigned index) {
    Method method = class_getInstanceMethod(cls, selector);
    if(!method) return NO;
    char type[128] = {};
    method_getArgumentType(method, index, type, sizeof(type));
    return type[0] == '@';
}

%ctor {
    ARITweakManager *manager = [ARITweakManager sharedInstance];
    if([manager firmwareVersion] != 18 || ![manager isEnabled] ||
       ![manager boolValueForKey:@"layoutEnabled"]) return;
    Class model = objc_getClass("SBIconListModel");
    Class list = objc_getClass("SBIconListView");
    Class map = objc_getClass("SBHIconGridSizeClassSizeMap");
    Method sizes = class_getInstanceMethod(model, @selector(gridSizeClassSizesWithOptions:));
    char returnType[128] = {};
    if(sizes) method_getReturnType(sizes, returnType, sizeof(returnType));
    if(returnType[0] != '@' ||
       !ARIObjectArgument18(model, @selector(gridSizeForGridSizeClass:), 2) ||
       !ARIObjectArgument18(list, @selector(iconGridSizeForClass:), 2) ||
       !class_getInstanceMethod(list, @selector(originForIconAtCoordinate:metrics:options:)) ||
       !class_getInstanceMethod(map, @selector(enumerateGridSizesUsingBlock:)) ||
       !class_getInstanceMethod(map, @selector(initWithGridSizeClassSizes:)) ||
       ![NSValue respondsToSelector:@selector(sbh_valueWithSBHIconGridSize:)]) {
        NSLog(@"[Atria]: iOS 18 widget interfaces unavailable; using system widget sizing.");
        return;
    }
    %init(Widgets18, ARIListModel18=model, ARIListView18=list);
}
