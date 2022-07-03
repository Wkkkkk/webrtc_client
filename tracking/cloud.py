import cv2
import numpy as np

def find_cloud_contour(img):
    # Find clouds in the image
    white = np.array([200, 200, 200])
    lowerBound = np.array([160,160,160])

    # Using inRange method, to create a mask
    mask = cv2.inRange(img, lowerBound, white)
    mask[:25, :] = 0

    # Generate contours based on our mask
    contours, _hierarchy = cv2.findContours(mask, 1, 2)

    return contours

# This function allows us to create a descending sorted list of contour areas.
def contour_area(contours):
     
    # create an empty list
    cnt_area = []
     
    # loop through all the contours
    for i in range(0,len(contours),1):
        # for each contour, use OpenCV to calculate the area of the contour
        cnt_area.append(cv2.contourArea(contours[i]))
 
    # Sort our list of contour areas in descending order
    list.sort(cnt_area, reverse=True)
    return cnt_area

def draw_bounding_box(contours, image, number_of_boxes=1):
    # Call our function to get the list of contour areas
    cnt_area = contour_area(contours)
 
    # Loop through each contour of our image
    for i in range(0,len(contours),1):
        cnt = contours[i]
 
        # Only draw the the largest number of boxes
        if (cv2.contourArea(cnt) > cnt_area[number_of_boxes]):
             
            # Use OpenCV boundingRect function to get the details of the contour
            x,y,w,h = cv2.boundingRect(cnt)
             
            # Draw the bounding box
            image=cv2.rectangle(image,(x,y),(x+w,y+h),(0,0,255),2)
 
    return image

if __name__ == '__main__':
    img = cv2.imread('clouds.png', 1)

    white = np.array([200, 200, 200])
    lowerBound = np.array([160,160,160])

    # Using inRange method, to create a mask
    mask = cv2.inRange(img, lowerBound, white)
    mask[:25, :] = 0

    # Generate contours based on our mask
    contours,hierarchy = cv2.findContours(mask, 1, 2)

    res = draw_bounding_box(contours, img, 3)

    cv2.imshow("mywindow",mask)

    cv2.waitKey(0)